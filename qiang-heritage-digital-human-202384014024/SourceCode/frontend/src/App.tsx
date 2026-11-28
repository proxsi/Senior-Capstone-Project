/* Coordinate the chat panel, digital-human state, graph focus, and upload modal.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import { useState, useRef } from 'react';
import ChatWindow from './components/ChatWindow';
import DigitalHuman from './components/DigitalHuman';
import type { DigitalHumanHandle } from './components/DigitalHuman';
import KnowledgeGraph from './components/KnowledgeGraph';
import KnowledgeBaseModal from './components/KnowledgeBaseModal';
import './App.css';

function App() {
  /**
   * Top-level shared state.
   * The entity mentioned in the most recent answer is owned here because two sibling
   * panels consume it: the avatar shows it as a caption and the graph centres on it.
   */
  const [currentEntity, setCurrentEntity] = useState<string>('');

  /** Visibility flag for the knowledge-base management modal. */
  const [showKnowledgeBase, setShowKnowledgeBase] = useState(false);

  /**
   * Imperative handle to the avatar.
   * ChatWindow cannot render DigitalHuman as a child, so conversation lifecycle events
   * are forwarded downward through this ref instead of through props.
   */
  const digitalHumanRef = useRef<DigitalHumanHandle>(null);

  /** An answer mentioned a heritage entity; store it so the graph can focus on that node. */
  const handleEntityMentioned = (entity: string) => {
    setCurrentEntity(entity);
  };

  /** A question was submitted and the backend is working; switch the avatar to "thinking". */
  const handleConversationStart = () => {
    digitalHumanRef.current?.startThinking();
  };

  /**
   * Speech metadata is known; switch the avatar to the talking clip.
   * The duration keeps the clip running roughly as long as the audio so the lips and
   * the voice stay loosely in sync.
   */
  const handleAudioStart = (duration: number) => {
    digitalHumanRef.current?.startTalking(duration);
  };

  /** Speech ended or failed; return the avatar to its idle standby loop. */
  const handleConversationEnd = () => {
    digitalHumanRef.current?.endConversation();
  };

  return (
    <div className="min-h-screen bg-qiangDark text-white">
      <header className="bg-gradient-to-r from-qiangRed to-qiangRed/80 shadow-lg">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="text-2xl">🏮</div>
            <h1 className="text-xl font-bold">羌智传承非遗问答系统</h1>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setShowKnowledgeBase(true)}
              className="text-sm hover:text-gray-200 transition-colors px-3 py-1 rounded bg-white/10 hover:bg-white/20"
            >
              羌族文化知识库
            </button>
          </div>
        </div>
      </header>

      {/*
        Three-column workspace on wide screens (chat / avatar / graph) that collapses to a
        single stacked column below the `xl` breakpoint. Explicit min-widths stop the avatar
        column from being squeezed by long answer text, while the fixed viewport heights keep
        all three panels aligned and independently scrollable.
      */}
      <main className="max-w-[1720px] mx-auto px-4 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-[minmax(350px,1fr)_minmax(340px,0.68fr)_minmax(330px,0.88fr)] gap-4 xl:gap-5 items-stretch">
          <div className="h-[74vh] xl:h-[78vh] min-h-[700px]">
            <ChatWindow
              onEntityMentioned={handleEntityMentioned}
              onConversationStart={handleConversationStart}
              onAudioStart={handleAudioStart}
              onConversationEnd={handleConversationEnd}
            />
          </div>

          <div className="h-[74vh] xl:h-[78vh] min-h-[700px]">
            <DigitalHuman ref={digitalHumanRef} entity={currentEntity} />
          </div>

          <div className="h-[74vh] xl:h-[78vh] min-h-[700px]">
            <KnowledgeGraph entity={currentEntity} />
          </div>
        </div>
      </main>

      <footer className="bg-gray-900 border-t border-gray-800 py-4 mt-8">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <p>© 2026 羌智传承非遗问答系统 | 基于知识图谱和人工智能技术</p>
          <p className="mt-1">保护羌族非物质文化遗产，传承中华民族优秀传统文化</p>
          <p className="mt-1">本项目由陕西理工大学刘逸鸣独立开发</p>
        </div>
      </footer>

      {/* Mounted permanently but renders nothing while closed, preserving its local tab state. */}
      <KnowledgeBaseModal
        isOpen={showKnowledgeBase}
        onClose={() => setShowKnowledgeBase(false)}
      />
    </div>
  );
}

export default App;
