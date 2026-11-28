/* Switch prerecorded video clips in response to conversation state.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import { useState, useRef, useEffect, useCallback, forwardRef, useImperativeHandle } from 'react';

/**
 * The avatar is a small state machine over prerecorded clips:
 *   welcome -> standby <-> thinking -> talking -> standby
 * All clips are muted loops of video; the real speech is played separately by ChatWindow.
 */
type DigitalHumanState = 'welcome' | 'standby' | 'thinking' | 'talking';
/** The standby state alternates between two clips to avoid an obvious hard cut. */
type StandbyVideoIndex = 0 | 1;

/** Imperative surface exposed to App so ChatWindow-driven events can move the avatar. */
export interface DigitalHumanHandle {
  startThinking: () => void;
  startTalking: (duration: number) => void;
  endConversation: () => void;
}

interface DigitalHumanProps {
  /** Entity currently being discussed; only used for the caption under the video. */
  entity?: string;
}

/**
 * Remote clip catalogue, grouped by state.
 * Standby and thinking each have two variants so the loop can cycle; only one talking clip
 * is used and it is played on a `loop` because speech length is unpredictable.
 */
const VIDEO_URLS = {
  welcome: 'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/kaichanghuanyingdonghua.mp4',
  standby: [
    'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/daijidonghua1.mp4',
    'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/daijidonghua2.mp4'
  ],
  thinking: [
    'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/Thinking01.mp4',
    'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/Thinking02.mp4'
  ],
  talk: 'https://slgwcf.oss-cn-beijing.aliyuncs.com/liuyiming/Talk.mp4'
};

const DigitalHuman = forwardRef<DigitalHumanHandle, DigitalHumanProps>(({ entity }, ref) => {
  /** Current clip category; drives the caption text and whether the video loops. */
  const [state, setState] = useState<DigitalHumanState>('welcome');
  /** Source of the visible <video>. Changing it remounts the element via the `key` prop. */
  const [currentVideoUrl, setCurrentVideoUrl] = useState(VIDEO_URLS.welcome);
  const videoRef = useRef<HTMLVideoElement>(null);
  /** Records that the opening clip has completed; kept as explicit state for future logic. */
  const welcomePlayedRef = useRef(false);
  /** Which standby variant is showing; flipped on every `ended` event. */
  const standbyIndexRef = useRef<StandbyVideoIndex>(0);
  /** How many times the thinking intro has been replayed before settling on the loop clip. */
  const thinkingIntroPlayedRef = useRef(0);
  /** Mirror of `state` for use inside event handlers, which close over stale state. */
  const stateRef = useRef<DigitalHumanState>('welcome');
  /** Mirror of `currentVideoUrl`, used by `handleVideoEnded` to identify the clip. */
  const currentVideoUrlRef = useRef(VIDEO_URLS.welcome);

  // Keep the mirrors in sync with React state; these effects have no cleanup by design.
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    currentVideoUrlRef.current = currentVideoUrl;
  }, [currentVideoUrl]);

  /**
   * Warm every clip once on mount.
   * A detached <video> element is created per URL so the browser fetches and buffers the file;
   * mounting the real element later then starts playback immediately instead of stalling.
   * Cleanup releases the decoders and the network buffers to avoid leaks on unmount.
   */
  useEffect(() => {
    const urls = [
      VIDEO_URLS.welcome,
      ...VIDEO_URLS.standby,
      ...VIDEO_URLS.thinking,
      VIDEO_URLS.talk
    ];

    const preloaders = urls.map((url) => {
      const video = document.createElement('video');
      video.preload = 'auto';
      video.muted = true;
      video.playsInline = true;
      video.src = url;
      return video;
    });

    return () => {
      preloaders.forEach((video) => {
        video.pause();
        video.removeAttribute('src');
        video.load();
      });
    };
  }, []);

  /** Restart the visible clip from the beginning. `play()` returns a promise that can reject. */
  const playCurrentVideo = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    video.currentTime = 0;
    const playPromise = video.play();
    if (playPromise) {
      playPromise.catch((error) => {
        console.error('数字人视频播放失败:', error);
      });
    }
  }, []);

  /** Replay without changing the source; used to extend the thinking animation. */
  const replayCurrentVideo = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    video.pause();
    video.currentTime = 0;
    const playPromise = video.play();
    if (playPromise) {
      playPromise.catch((error) => {
        console.error('数字人视频重播失败:', error);
      });
    }
  }, []);

  /** Switch state and source in one batch so the caption and the clip never disagree. */
  const switchVideo = useCallback((nextState: DigitalHumanState, url: string) => {
    setState(nextState);
    setCurrentVideoUrl(url);
  }, []);

  /** Enter standby with a specific variant and reset the thinking replay counter. */
  const switchToStandby = useCallback((index: StandbyVideoIndex) => {
    standbyIndexRef.current = index;
    thinkingIntroPlayedRef.current = 0;
    switchVideo('standby', VIDEO_URLS.standby[index]);
  }, [switchVideo]);

  // Autoplay whenever the source changes; `playCurrentVideo` is memoised so this is stable.
  useEffect(() => {
    playCurrentVideo();
  }, [currentVideoUrl, playCurrentVideo]);

  /**
   * Clip scheduler. Called for every `ended` event:
   * - welcome plays once, then hands over to standby;
   * - standby alternates between its two variants forever;
   * - thinking replays its intro clip twice, then loops the second clip - this keeps the
   *   "thinking" animation alive for as long as the backend takes;
   * - talking is a looping element, so it should not reach here.
   */
  const handleVideoEnded = useCallback(() => {
    const currentState = stateRef.current;
    const currentUrl = currentVideoUrlRef.current;

    if (currentState === 'welcome') {
      welcomePlayedRef.current = true;
      switchToStandby(0);
      return;
    }

    if (currentState === 'standby') {
      const nextIndex: StandbyVideoIndex = standbyIndexRef.current === 0 ? 1 : 0;
      standbyIndexRef.current = nextIndex;
      switchVideo('standby', VIDEO_URLS.standby[nextIndex]);
      return;
    }

    if (currentState === 'thinking') {
      if (currentUrl === VIDEO_URLS.thinking[0] && thinkingIntroPlayedRef.current < 2) {
        thinkingIntroPlayedRef.current += 1;
        replayCurrentVideo();
        return;
      }

      if (currentUrl === VIDEO_URLS.thinking[1]) {
        replayCurrentVideo();
        return;
      }

      switchVideo('thinking', VIDEO_URLS.thinking[1]);
    }
  }, [replayCurrentVideo, switchToStandby, switchVideo]);

  /** Enter the thinking state from the beginning whenever a new question is submitted. */
  const startThinking = useCallback(() => {
    thinkingIntroPlayedRef.current = 0;
    switchVideo('thinking', VIDEO_URLS.thinking[0]);
  }, [switchVideo]);

  /**
   * Enter the talking state.
   * `_duration` is accepted for interface symmetry with the caller but intentionally unused:
   * the clip loops and `endConversation` is what actually stops it. If the talking clip is
   * already showing, replay it rather than remounting the element.
   */
  const startTalking = useCallback((_duration: number) => {
    const video = videoRef.current;
    if (stateRef.current === 'talking' && currentVideoUrlRef.current === VIDEO_URLS.talk && video) {
      replayCurrentVideo();
      return;
    }

    switchVideo('talking', VIDEO_URLS.talk);
  }, [replayCurrentVideo, switchVideo]);

  /** Speech finished or failed; drop back to the first standby clip. */
  const endConversation = useCallback(() => {
    switchToStandby(0);
  }, [switchToStandby]);

  // Expose state transitions to the parent; speech controls timing while videos are prerecorded.
  useImperativeHandle(ref, () => ({
    startThinking,
    startTalking,
    endConversation
  }), [startThinking, startTalking, endConversation]);

  return (
    <div className="flex flex-col h-full bg-gray-900 rounded-lg shadow-lg overflow-hidden border border-gray-800">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800 bg-gradient-to-r from-gray-800 to-gray-900">
        <h3 className="text-sm font-semibold text-gray-100">羌羌</h3>
        <div className="text-[11px] text-gray-400">羌族文化大使</div>
      </div>

      <div className="flex-[1_1_auto] flex items-center justify-center px-0.5 py-2 min-h-0 bg-gradient-to-b from-gray-950 via-black to-gray-950">
        <div className="relative h-full aspect-[9/16] w-auto max-w-full overflow-hidden rounded-[28px] border-[3px] border-qiangRed/50 bg-black shadow-[0_0_24px_rgba(215,38,56,0.18)]">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(215,38,56,0.14),transparent_45%)] pointer-events-none"></div>
          <video
            ref={videoRef}
            // Changing the key forces a fresh element, which is what makes the source swap
            // take effect reliably across browsers.
            key={currentVideoUrl}
            className="w-full h-full object-contain bg-black"
            muted
            autoPlay
            playsInline
            preload="auto"
            // Only the talking clip loops; the others hand over via `onEnded`.
            loop={state === 'talking'}
            onEnded={handleVideoEnded}
            src={currentVideoUrl}
          />
          {/* Decorative "online" indicator. */}
          <div className="absolute bottom-2 right-2 w-2.5 h-2.5 bg-green-500 rounded-full animate-pulse border border-gray-900"></div>
        </div>
      </div>

      {/* Caption strip. Exactly one branch is truthy because `state` is a union. */}
      <div className="px-3 py-1.5 border-t border-gray-800 bg-gray-800/55">
        <div className="text-center">
          <h4 className="text-sm font-semibold text-gray-100">羌族文化数字大使</h4>
          <p className="text-[11px] text-gray-400 leading-4 min-h-[16px] mt-0.5">
            {state === 'welcome' && '欢迎观看'}
            {state === 'standby' && (entity ? `正在为您介绍 ${entity}` : '随时为您解答羌族文化问题')}
            {state === 'thinking' && '正在思考中...'}
            {state === 'talking' && '正在回答...'}
          </p>
        </div>
      </div>
    </div>
  );
});

DigitalHuman.displayName = 'DigitalHuman';

export default DigitalHuman;
