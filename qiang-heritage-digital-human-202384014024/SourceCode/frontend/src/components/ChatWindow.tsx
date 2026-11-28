/* Chat interaction, image attachments, simulated typing, and speech playback.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Volume2, VolumeX, ImagePlus, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { ChatMessage } from '../api/chat';
import { sendChatMessage, synthesizeSpeech } from '../api/chat';

interface ChatWindowProps {
  /** Called with every heritage entity detected in an answer, so the graph can refocus. */
  onEntityMentioned: (entity: string) => void;
  /** Called when a question is sent; drives the avatar's "thinking" state. */
  onConversationStart?: () => void;
  /** Called once playback metadata is known, carrying the clip length in seconds. */
  onAudioStart?: (duration: number) => void;
  /** Called when speech finishes, fails, or is stopped; returns the avatar to idle. */
  onConversationEnd?: () => void;
}

/** Fallback clip length when the browser cannot report a decoded duration. */
const AUDIO_DURATION_SECONDS = 12;
/** Greeting shown before the user has asked anything, paired with the bundled MP3. */
const INITIAL_WELCOME_TEXT = '纳吉纳鲁，我是羌羌，欢迎你来。';
/** Static greeting audio served from the Vite public directory. */
const INITIAL_WELCOME_AUDIO_SRC = '/welcome.mp3';
/**
 * Pseudo-progress captions cycled while the single blocking /chat request is in flight.
 * These are cosmetic only - the backend reports no milestone events.
 */
const LOADING_STAGES = [
  '正在检索知识库...',
  '正在联网搜索...',
  '正在组织回答...',
  '数字人正在思考中...'
];

const ChatWindow: React.FC<ChatWindowProps> = ({
  onEntityMentioned,
  onConversationStart,
  onAudioStart,
  onConversationEnd
}) => {
  /** Confirmed transcript. A new array identity is pushed on every append to trigger re-render. */
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  /** Controlled textarea value. */
  const [input, setInput] = useState('');
  /** True while the /chat request is outstanding; disables input and drives the ticker. */
  const [loading, setLoading] = useState(false);
  /** True while the answer is being revealed character by character. */
  const [streaming, setStreaming] = useState(false);
  /** The partial answer currently being revealed; not yet part of `messages`. */
  const [streamingContent, setStreamingContent] = useState('');
  /** Caption from LOADING_STAGES shown next to the spinner. */
  const [loadingMessage, setLoadingMessage] = useState('');
  /** Whether any clip is playing, used to swap the speaker icon. */
  const [isSpeaking, setIsSpeaking] = useState(false);
  /** Id of the message whose clip is playing, so only that row shows the stop icon. */
  const [currentSpeakingId, setCurrentSpeakingId] = useState<string | null>(null);
  /** Master voice switch; when false no TTS request is made and autoplay is skipped. */
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  /** Fallback button shown when autoplay is blocked by the browser. */
  const [showWelcomeAudioPrompt, setShowWelcomeAudioPrompt] = useState(false);
  /** Data URL used for the attachment thumbnail in the composer and transcript. */
  const [selectedImagePreview, setSelectedImagePreview] = useState<string | null>(null);
  /** Raw base64 payload (no `data:` prefix) sent to the backend. */
  const [selectedImageBase64, setSelectedImageBase64] = useState<string | null>(null);
  /** MIME type of the attached image, forwarded alongside the base64 payload. */
  const [selectedImageMimeType, setSelectedImageMimeType] = useState<string | null>(null);
  /** Zero-height sentinel rendered after the last bubble; scrolling it into view pins the list. */
  const messagesEndRef = useRef<HTMLDivElement>(null);
  /** Hidden `<input type="file">` opened programmatically by the paperclip button. */
  const fileInputRef = useRef<HTMLInputElement>(null);
  /** The single audio element allowed to play at a time (TTS clip or welcome clip). */
  const currentSourceRef = useRef<HTMLAudioElement | null>(null);
  /** Pre-mounted element for the bundled greeting so the MP3 is decoded before it is needed. */
  const welcomeAudioRef = useRef<HTMLAudioElement | null>(null);
  /** Guards against firing onAudioStart twice for one clip (metadata + play both fire). */
  const audioStartCalledRef = useRef(false);
  /** Interval id for the loading ticker; cleared on unmount and on every new request. */
  const loadingTimerRef = useRef<number | null>(null);
  /** Ensures the greeting bubble is seeded only once, even under StrictMode double-invocation. */
  const welcomePlayedRef = useRef(false);
  /** True when autoplay was rejected, so the first user gesture should retry playback. */
  const welcomeAudioPendingRef = useRef(false);

  /** Pin the transcript to the newest content after every append or streamed character. */
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Re-runs on both confirmed messages and the in-flight partial answer, since either can grow.
  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent]);

  // Decode the bundled greeting once on mount; the element itself stays hidden in the tree.
  useEffect(() => {
    const welcomeAudio = welcomeAudioRef.current;
    if (!welcomeAudio) return;
    welcomeAudio.load();
  }, []);

  /**
   * Seed the transcript with the greeting and try to autoplay its audio.
   * The ref guard makes this idempotent across StrictMode's mount/unmount/mount cycle.
   * The 700 ms delay lets the panel finish its first paint before audio starts.
   */
  useEffect(() => {
    if (welcomePlayedRef.current) return;

    welcomePlayedRef.current = true;

    const welcomeMessage: ChatMessage = {
      id: `welcome-${Date.now()}`,
      role: 'assistant',
      content: INITIAL_WELCOME_TEXT,
      source_type: 'llm',
      timestamp: Date.now(),
    };

    const timer = window.setTimeout(async () => {
      setMessages([welcomeMessage]);

      if (!voiceEnabled) {
        welcomeAudioPendingRef.current = false;
        setShowWelcomeAudioPrompt(false);
        return;
      }

      try {
        await playWelcomeAudio(welcomeMessage.id);
      } catch (error) {
        console.error('初始欢迎语音播放失败:', error);
      }
    }, 700);

    // Cancelling the pending timer prevents a state update after unmount.
    return () => window.clearTimeout(timer);
  }, [voiceEnabled]);

  /**
   * Autoplay recovery.
   * Browsers block audio until the user interacts with the page, so if the greeting was
   * rejected (`welcomeAudioPendingRef`) the first pointer/key event retries it once, then
   * removes both listeners. The `once` option plus manual removal keeps the teardown safe.
   */
  useEffect(() => {
    const replayWelcomeAudio = async () => {
      if (!voiceEnabled || !welcomeAudioPendingRef.current || messages.length === 0) {
        return;
      }

      const welcomeMessage = messages[0];
      if (welcomeMessage?.role !== 'assistant' || welcomeMessage.content !== INITIAL_WELCOME_TEXT) {
        return;
      }

      try {
        await playWelcomeAudio(welcomeMessage.id);
      } catch (error) {
        console.error('补播欢迎语音失败:', error);
      }
    };

    const handleFirstInteraction = () => {
      replayWelcomeAudio();
      window.removeEventListener('pointerdown', handleFirstInteraction);
      window.removeEventListener('keydown', handleFirstInteraction);
    };

    window.addEventListener('pointerdown', handleFirstInteraction, { once: true });
    window.addEventListener('keydown', handleFirstInteraction, { once: true });

    return () => {
      window.removeEventListener('pointerdown', handleFirstInteraction);
      window.removeEventListener('keydown', handleFirstInteraction);
    };
  }, [messages, voiceEnabled]);

  // Safety net: the component can unmount mid-request, so the ticker interval must be released.
  useEffect(() => {
    return () => {
      if (loadingTimerRef.current) {
        window.clearInterval(loadingTimerRef.current);
      }
    };
  }, []);

  /**
   * Start cycling the fake progress captions.
   * Any previous interval is cleared first so overlapping requests cannot leave two timers
   * writing to the same state slot.
   */
  const startLoadingStages = () => {
    let index = 0;
    setLoadingMessage(LOADING_STAGES[0]);

    if (loadingTimerRef.current) {
      window.clearInterval(loadingTimerRef.current);
    }

    loadingTimerRef.current = window.setInterval(() => {
      // Clamp at the final caption; the list is never looped because the request is one-shot.
      index = Math.min(index + 1, LOADING_STAGES.length - 1);
      setLoadingMessage(LOADING_STAGES[index]);
    }, 1200);
  };

  /** Stop the caption ticker and hide the spinner row. */
  const stopLoadingStages = () => {
    if (loadingTimerRef.current) {
      window.clearInterval(loadingTimerRef.current);
      loadingTimerRef.current = null;
    }
    setLoadingMessage('');
  };

  /**
   * Play synthesized speech for one answer and notify the digital-human state callbacks.
   * Pressing the icon of the message that is already playing acts as a stop toggle.
   */
  const playAudio = async (text: string, messageId: string) => {
    try {
      if (currentSpeakingId === messageId && isSpeaking) {
        stopAudio();
        return;
      }

      stopAudio();

      setIsSpeaking(true);
      setCurrentSpeakingId(messageId);
      audioStartCalledRef.current = false;

      const response = await synthesizeSpeech(text);

      if (!response || !response.audio) {
        setIsSpeaking(false);
        setCurrentSpeakingId(null);
        return;
      }

      // atob yields a binary string; Uint8Array converts it to the bytes Blob expects.
      const audioData = Uint8Array.from(atob(response.audio), c => c.charCodeAt(0));
      const audioBlob = new Blob([audioData], { type: 'audio/mp3' });
      const audioUrl = URL.createObjectURL(audioBlob);

      const audio = new Audio(audioUrl);
      currentSourceRef.current = audio;

      // `loadedmetadata` is not guaranteed before `play()` resolves, hence the shared guard.
      audio.onloadedmetadata = () => {
        if (!audioStartCalledRef.current) {
          audioStartCalledRef.current = true;
          onAudioStart?.(audio.duration || AUDIO_DURATION_SECONDS);
        }
      };

      // Both terminal handlers revoke the object URL to avoid leaking blob memory.
      audio.onended = () => {
        setIsSpeaking(false);
        setCurrentSpeakingId(null);
        URL.revokeObjectURL(audioUrl);
        onConversationEnd?.();
      };

      audio.onerror = () => {
        setIsSpeaking(false);
        setCurrentSpeakingId(null);
        URL.revokeObjectURL(audioUrl);
        onConversationEnd?.();
      };

      await audio.play();

      // Some browsers fire `play()` before duration is known; fall back to the constant.
      if (!audioStartCalledRef.current) {
        audioStartCalledRef.current = true;
        onAudioStart?.(AUDIO_DURATION_SECONDS);
      }

    } catch (error) {
      console.error('播放语音失败:', error);
      setIsSpeaking(false);
      setCurrentSpeakingId(null);
    }
  };

  /**
   * Detach and reset whatever clip is currently playing.
   * Callbacks are nulled before the reference is dropped so a pending `ended` event cannot
   * fire after the user has already moved on to another message.
   */
  const stopAudio = () => {
    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.pause();
        currentSourceRef.current.currentTime = 0;
        currentSourceRef.current.onended = null;
        currentSourceRef.current.onerror = null;
        currentSourceRef.current.onloadedmetadata = null;
      } catch (e) {}
      currentSourceRef.current = null;
    }
    setIsSpeaking(false);
    setCurrentSpeakingId(null);
  };

  /**
   * Play the bundled greeting MP3 from a pre-mounted <audio> element.
   * Unlike TTS clips there is no fetch step, but the same callback contract applies.
   * If the browser rejects autoplay, the pending flag makes the retry-on-gesture effect fire.
   */
  const playWelcomeAudio = async (messageId: string) => {
    stopAudio();
    setIsSpeaking(true);
    setCurrentSpeakingId(messageId);
    audioStartCalledRef.current = false;

    const audio = welcomeAudioRef.current;
    if (!audio) {
      setIsSpeaking(false);
      setCurrentSpeakingId(null);
      welcomeAudioPendingRef.current = true;
      setShowWelcomeAudioPrompt(true);
      throw new Error('欢迎音频元素不存在');
    }

    currentSourceRef.current = audio;
    audio.currentTime = 0;

    audio.onloadedmetadata = () => {
      audioStartCalledRef.current = true;
      onAudioStart?.(audio.duration || AUDIO_DURATION_SECONDS);
    };

    audio.onended = () => {
      setIsSpeaking(false);
      setCurrentSpeakingId(null);
      welcomeAudioPendingRef.current = false;
      setShowWelcomeAudioPrompt(false);
      onConversationEnd?.();
    };

    // A failed greeting keeps the manual replay button visible instead of silently dying.
    audio.onerror = () => {
      setIsSpeaking(false);
      setCurrentSpeakingId(null);
      welcomeAudioPendingRef.current = true;
      setShowWelcomeAudioPrompt(true);
      onConversationEnd?.();
    };

    try {
      const playPromise = audio.play();
      if (playPromise) {
        await playPromise;
      }
      welcomeAudioPendingRef.current = false;
      setShowWelcomeAudioPrompt(false);
      if (!audioStartCalledRef.current) {
        audioStartCalledRef.current = true;
        onAudioStart?.(audio.duration || AUDIO_DURATION_SECONDS);
      }
      return true;
    } catch (error) {
      setIsSpeaking(false);
      setCurrentSpeakingId(null);
      welcomeAudioPendingRef.current = true;
      setShowWelcomeAudioPrompt(true);
      throw error;
    }
  };

  /**
   * Reveal the completed answer locally while requesting and playing its speech.
   * This is deliberately NOT model token streaming: the backend returns the whole answer in
   * one JSON body, so the text is typed out here at a fixed cadence to create the illusion
   * of generation while the TTS clip loads and plays.
   *
   * Two paths exist:
   * 1. Voice on and synthesis succeeds - start audio, type the text in parallel, and commit
   *    the message only when the audio ends (or errors), so the bubble and the voice agree.
   * 2. Voice off, or synthesis fails - just type the text, then commit the message.
   */
  const simulateStreamingWithAudio = async (
    content: string,
    sourceType: 'local' | 'web' | 'llm' | 'image',
    sourceUrl?: string
  ) => {
    const newMessageId = Date.now().toString();
    audioStartCalledRef.current = false;

    if (voiceEnabled) {
      try {
        const response = await synthesizeSpeech(content);

        if (response && response.audio) {
          const audioData = Uint8Array.from(atob(response.audio), c => c.charCodeAt(0));
          const audioBlob = new Blob([audioData], { type: 'audio/mp3' });
          const audioUrl = URL.createObjectURL(audioBlob);

          const audio = new Audio(audioUrl);
          currentSourceRef.current = audio;

          audio.onloadedmetadata = () => {
            if (!audioStartCalledRef.current) {
              audioStartCalledRef.current = true;
              onAudioStart?.(audio.duration || AUDIO_DURATION_SECONDS);
            }
          };

          // Commit the answer once playback ends; using the functional updater keeps any
          // messages that arrived in the meantime (e.g. a fast follow-up) intact.
          audio.onended = () => {
            setIsSpeaking(false);
            setCurrentSpeakingId(null);
            URL.revokeObjectURL(audioUrl);
            setStreaming(false);
            setMessages(prev => [...prev, {
              id: newMessageId,
              role: 'assistant',
              content,
              source_type: sourceType,
              source_url: sourceUrl,
              timestamp: Date.now(),
            }]);
            extractEntities(content);
            onConversationEnd?.();
          };

          // A silent audio failure must still show the answer, so this mirrors `onended`.
          audio.onerror = () => {
            setIsSpeaking(false);
            setCurrentSpeakingId(null);
            URL.revokeObjectURL(audioUrl);
            setStreaming(false);
            setMessages(prev => [...prev, {
              id: newMessageId,
              role: 'assistant',
              content,
              source_type: sourceType,
              source_url: sourceUrl,
              timestamp: Date.now(),
            }]);
            extractEntities(content);
            onConversationEnd?.();
          };

          setIsSpeaking(true);
          setCurrentSpeakingId(newMessageId);
          setStreaming(true);
          setStreamingContent('');

          await audio.play();

          if (!audioStartCalledRef.current) {
            audioStartCalledRef.current = true;
            onAudioStart?.(AUDIO_DURATION_SECONDS);
          }

          // ~28 characters per second; the interval stops itself at the end of the string,
          // and the message is committed by the audio handlers rather than here.
          let index = 0;
          const interval = setInterval(() => {
            if (index < content.length) {
              setStreamingContent(prev => prev + content.charAt(index));
              index++;
            } else {
              clearInterval(interval);
            }
          }, 35);

          return;
        }
      } catch (err) {
        // Fall through to the silent typing path instead of dropping the answer.
        console.error('语音合成失败:', err);
      }
    }

    setStreaming(true);
    setStreamingContent('');

    // Silent path: type the answer, then move the finished text from `streamingContent`
    // into the transcript so the markdown bubble becomes permanent.
    let index = 0;
    const interval = setInterval(() => {
      if (index < content.length) {
        setStreamingContent(prev => prev + content.charAt(index));
        index++;
      } else {
        clearInterval(interval);
        setStreaming(false);
        setMessages(prev => [...prev, {
          id: newMessageId,
          role: 'assistant',
          content,
          source_type: sourceType,
          source_url: sourceUrl,
          timestamp: Date.now(),
        }]);
        extractEntities(content);
        onConversationEnd?.();
      }
    }, 35);
  };

  /**
   * Naive keyword scan over the answer text.
   * The first matching entity in the list wins for the graph highlight, because
   * onEntityMentioned is called for each hit and the last call overwrites the state.
   */
  const extractEntities = (content: string) => {
    const qiangEntities = ['羌绣', '羌族', '羌笛', '羌年', '羌族服饰', '羌族建筑', '羌族音乐', '羌族舞蹈'];
    qiangEntities.forEach(entity => {
      if (content.includes(entity)) {
        onEntityMentioned(entity);
      }
    });
  };

  /** Reset the attachment state and clear the file input so the same file can be re-picked. */
  const clearSelectedImage = () => {
    setSelectedImagePreview(null);
    setSelectedImageBase64(null);
    setSelectedImageMimeType(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  /**
   * Convert the chosen image to a data URL.
   * `FileReader.readAsDataURL` produces `data:<mime>;base64,<payload>`; the payload after the
   * first comma is what the backend expects, while the whole string is kept as the preview.
   * Only the first selected file is used - the input is not `multiple`.
   */
  const handleImageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result;
      if (typeof result !== 'string') return;
      const base64 = result.split(',')[1];
      setSelectedImagePreview(result);
      setSelectedImageBase64(base64 ?? null);
      setSelectedImageMimeType(file.type || 'image/jpeg');
    };
    reader.readAsDataURL(file);
  };

  /**
   * Submit one turn.
   *
   * Order matters: the user bubble is appended optimistically before the network call so the
   * transcript reacts instantly, and `messages` (the pre-send snapshot) is passed as history -
   * the newly appended turn travels separately as `query`, avoiding a duplicate.
   *
   * On failure a localised apology bubble is appended and the avatar is returned to idle;
   * the `finally` block always clears the ticker and the loading flag so the composer
   * cannot get stuck if either the request or the streaming step throws.
   */
  const handleSend = async () => {
    if ((!input.trim() && !selectedImageBase64) || loading) return;

    const trimmedInput = input.trim();
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      // An image-only turn still needs text for the model, hence the fixed caption.
      content: trimmedInput || '请帮我看看这张图片。',
      image_preview: selectedImagePreview || undefined,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);
    startLoadingStages();
    onConversationStart?.();

    try {
      const response = await sendChatMessage(
        trimmedInput || '请帮我看看这张图片。',
        messages,
        selectedImageBase64 ?? undefined,
        selectedImageMimeType ?? undefined
      );

      clearSelectedImage();
      stopLoadingStages();
      setLoading(false);
      await simulateStreamingWithAudio(response.answer, response.source_type, response.reference);
    } catch (error) {
      console.error('发送消息失败:', error);
      clearSelectedImage();
      stopLoadingStages();
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: '抱歉，处理您的请求时出现错误，请稍后再试。',
        source_type: 'llm',
        timestamp: Date.now(),
      }]);
      onConversationEnd?.();
    } finally {
      stopLoadingStages();
      setLoading(false);
    }
  };

  /** Enter sends; Shift+Enter keeps the default newline behaviour. */
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  /** Render the coloured provenance badge; `llm` means no retrieval source was used. */
  const renderSourceTag = (message: ChatMessage) => {
    if (!message.source_type) return null;

    switch (message.source_type) {
      case 'local':
        return (
          <div className="flex items-center gap-1 text-xs text-green-500 mt-1">
            <span className="w-2 h-2 bg-green-500 rounded-full"></span>
            <span>来源：本地非遗库</span>
          </div>
        );
      case 'web':
        return (
          <div className="flex items-center gap-1 text-xs text-blue-500 mt-1">
            <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
            <span>来源：互联网搜索</span>
          </div>
        );
      case 'image':
        return (
          <div className="flex items-center gap-1 text-xs text-amber-400 mt-1">
            <span className="w-2 h-2 bg-amber-400 rounded-full"></span>
            <span>来源：图片解析</span>
          </div>
        );
      case 'llm':
        return (
          <div className="flex items-center gap-1 text-xs text-purple-400 mt-1">
            <span className="w-2 h-2 bg-purple-400 rounded-full"></span>
            <span>来源：羌羌自主回复</span>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg border border-gray-800 shadow-lg overflow-hidden">
      {/*
        Hidden, always-mounted element for the bundled greeting. It is preloaded rather than
        created on demand so the first greeting has no network latency, and it is reused on
        replay instead of allocating a new object URL.
      */}
      <audio
        ref={welcomeAudioRef}
        src={INITIAL_WELCOME_AUDIO_SRC}
        preload="auto"
        playsInline
      />
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        <h2 className="text-base font-semibold text-white">智能对话</h2>
        {/* Master voice toggle; turning it off also halts whatever is currently playing. */}
        <button
          onClick={() => {
            setVoiceEnabled(!voiceEnabled);
            if (voiceEnabled) stopAudio();
          }}
          className={`p-2 rounded-full transition-colors ${voiceEnabled ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}`}
          title={voiceEnabled ? '语音已开启，点击关闭' : '语音已关闭，点击开启'}
        >
          {voiceEnabled ? (
            <Volume2 className="w-5 h-5 text-white" />
          ) : (
            <VolumeX className="w-5 h-5 text-white" />
          )}
        </button>
      </div>

      {/* Scroll container: the only flexible row, so the header and composer stay pinned. */}
      <div className="flex-1 overflow-y-auto p-3 xl:p-4 space-y-4">
        {/* Empty-state hint shown before the greeting has been seeded. */}
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500">
            <div className="text-4xl mb-4">🏮</div>
            <h3 className="text-xl font-semibold mb-2">欢迎使用羌智传承非遗问答系统</h3>
            <p className="text-center max-w-md">
              您可以询问关于羌族非物质文化遗产的问题，如羌绣、羌笛、羌年等
            </p>
          </div>
        )}

        {/* Manual replay affordance for browsers that blocked the greeting's autoplay. */}
        {showWelcomeAudioPrompt && messages.length > 0 && (
          <div className="flex justify-start -mb-1">
            <button
              onClick={() => playWelcomeAudio(messages[0].id)}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs rounded-full border border-amber-400/30 bg-amber-500/10 text-amber-200 hover:bg-amber-500/15 transition-colors"
              title="播放欢迎语音"
            >
              <Volume2 className="w-3.5 h-3.5" />
              点击播放欢迎语
            </button>
          </div>
        )}

        {/* Confirmed transcript. Each bubble is keyed by its message id so React can
            reconcile appends without re-rendering the whole list. */}
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} mb-4`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg text-left ${message.role === 'user'
                ? 'bg-qiangBlue/20 text-white rounded-tr-none'
                : 'bg-gray-800 text-gray-100 rounded-tl-none'}`}
            >
              {message.image_preview && (
                <img
                  src={message.image_preview}
                  alt="用户上传"
                  className="mb-3 max-h-56 rounded-lg border border-white/10 object-cover"
                />
              )}
              <div className="markdown-body">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
              <div className="flex items-center justify-between mt-1">
                {renderSourceTag(message)}
                {message.role === 'assistant' && voiceEnabled && (
                  <button
                    onClick={() => playAudio(message.content, message.id)}
                    className="p-1 hover:bg-gray-700 rounded transition-colors"
                    title={currentSpeakingId === message.id && isSpeaking ? '停止播放' : '播放语音'}
                  >
                    {currentSpeakingId === message.id && isSpeaking ? (
                      <VolumeX className="w-4 h-4 text-qiangRed" />
                    ) : (
                      <Volume2 className="w-4 h-4 text-gray-400 hover:text-white" />
                    )}
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}

        {/* In-flight partial answer, rendered with the same markdown pipeline as final bubbles. */}
        {streaming && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[80%] p-3 rounded-lg bg-gray-800 text-gray-100 rounded-tl-none text-left">
              <div className="markdown-body">
                <ReactMarkdown>{streamingContent}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}

        {/* Spinner row with the rotating LOADING_STAGES caption. */}
        {loading && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[80%] p-3 rounded-lg bg-gray-800 text-gray-100 rounded-tl-none flex items-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>{loadingMessage}</span>
            </div>
          </div>
        )}

        {/* Auto-scroll sentinel: scrolled into view whenever the transcript grows. */}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer: attachment preview, hidden file input, and the send row. */}
      <div className="p-4 border-t border-gray-700">
        <input
          ref={fileInputRef}
          id="chat-image-upload"
          name="chat-image-upload"
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleImageChange}
        />

        {/* Local thumbnail of the pending attachment; removing it also clears the base64 state. */}
        {selectedImagePreview && (
          <div className="mb-3 relative inline-block">
            <img
              src={selectedImagePreview}
              alt="待发送图片"
              className="max-h-36 rounded-lg border border-gray-700 object-cover"
            />
            <button
              onClick={clearSelectedImage}
              className="absolute -top-2 -right-2 bg-black/80 hover:bg-black text-white rounded-full p-1"
              title="移除图片"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <div className="flex gap-2">
          {/* Opens the hidden file input; disabled while a turn is in flight. */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading || streaming}
            className="bg-gray-800 hover:bg-gray-700 disabled:bg-gray-700 text-white px-3 py-2 rounded-lg transition-colors"
            title="上传图片"
          >
            <ImagePlus className="w-5 h-5" />
          </button>
          <textarea
            id="chat-input"
            name="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="请输入您的问题，或上传图片让羌羌帮你看看..."
            className="flex-1 bg-gray-800 text-white rounded-lg px-4 py-2 resize-none focus:outline-none focus:ring-2 focus:ring-qiangBlue"
            rows={1}
            disabled={loading || streaming}
          />
          {/* Send is blocked until there is text or an image, and while streaming. */}
          <button
            onClick={handleSend}
            disabled={(!input.trim() && !selectedImageBase64) || loading || streaming}
            className="bg-qiangBlue hover:bg-qiangBlue/80 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg transition-colors"
          >
            <Send className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
