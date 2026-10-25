// Load the editor runtime only after the user opens or creates a file. Welcome,
// authentication, and the empty workspace do not need its language services.
import * as monaco from 'monaco-editor';
import Editor, { loader } from '@monaco-editor/react';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

(self as typeof self & { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};
loader.config({ monaco });
monaco.editor.defineTheme('qore', {
  base: 'vs-dark', inherit: true,
  rules: [
    { token: 'comment', foreground: '7F8BA5' },
    { token: 'keyword', foreground: 'AB96FF' },
    { token: 'string', foreground: '9AD9B5' },
    { token: 'number', foreground: 'F5CD89' },
  ],
  colors: {
    'editor.background': '#0B101C', 'editor.foreground': '#DCE5F5',
    'editorLineNumber.foreground': '#58647E', 'editorLineNumber.activeForeground': '#57D9FF',
    'editorCursor.foreground': '#57D9FF', 'editor.selectionBackground': '#234459',
    'editor.lineHighlightBackground': '#131C2C', 'editorIndentGuide.background1': '#1A263B',
  },
});

export default Editor;
