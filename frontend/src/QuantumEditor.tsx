// Load the editor runtime only after the user opens or creates a file. Welcome,
// authentication, and the empty workspace do not need its language services.
import * as monaco from 'monaco-editor';
import Editor, { loader } from '@monaco-editor/react';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

(self as typeof self & { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};
loader.config({ monaco });
monaco.languages.register({ id: 'qsharp', extensions: ['.qs'], aliases: ['Q#', 'qsharp'] });
monaco.languages.setMonarchTokensProvider('qsharp', {
  keywords: ['namespace', 'open', 'operation', 'function', 'use', 'borrow', 'let', 'mutable', 'set', 'return', 'if', 'elif', 'else', 'for', 'in', 'while', 'repeat', 'until', 'fixup', 'within', 'apply', 'body', 'adjoint', 'controlled', 'Adjoint', 'Controlled', 'is'],
  typeKeywords: ['Qubit', 'Result', 'Unit', 'Int', 'Double', 'Bool', 'String', 'Pauli', 'Range', 'Zero', 'One', 'true', 'false'],
  tokenizer: {
    root: [
      [/\/\//, 'comment', '@lineComment'],
      [/\/\*/, 'comment', '@comment'],
      [/"/, 'string', '@string'],
      [/@[A-Za-z_]\w*/, 'annotation'],
      [/[A-Za-z_]\w*/, { cases: { '@keywords': 'keyword', '@typeKeywords': 'type', '@default': 'identifier' } }],
      [/\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/, 'number'],
      [/[{}()[\]]/, '@brackets'],
    ],
    lineComment: [[/.*$/, 'comment', '@pop']],
    comment: [[/[^/*]+/, 'comment'], [/\*\//, 'comment', '@pop'], [/[/*]/, 'comment']],
    string: [[/[^\\"]+/, 'string'], [/\\./, 'string.escape'], [/"/, 'string', '@pop']],
  },
});
monaco.editor.defineTheme('qore', {
  base: 'vs-dark', inherit: true,
  rules: [
    { token: '', foreground: 'E9E6E1' },
    { token: 'comment', foreground: '969594' },
    { token: 'keyword', foreground: 'F4F2EE', fontStyle: 'bold' },
    { token: 'type', foreground: 'D9D6D0' },
    { token: 'identifier', foreground: 'E9E6E1' },
    { token: 'function', foreground: 'E1DED8' },
    { token: 'annotation', foreground: 'C8C4BE' },
    { token: 'string', foreground: 'C8C4BE' },
    { token: 'number', foreground: 'D7D3CC' },
    { token: 'operator', foreground: 'B8B5B0' },
  ],
  colors: {
    'editor.background': '#111112', 'editor.foreground': '#E9E6E1',
    'editorLineNumber.foreground': '#777779', 'editorLineNumber.activeForeground': '#F4F2EE',
    'editorCursor.foreground': '#F4F2EE', 'editor.selectionBackground': '#6B696B77',
    'editor.inactiveSelectionBackground': '#5B595B55', 'editor.selectionHighlightBackground': '#77747733',
    'editor.lineHighlightBackground': '#FFFFFF0B', 'editorLineHighlightBorder': '#FFFFFF0B',
    'editorIndentGuide.background1': '#49494B', 'editorIndentGuide.activeBackground1': '#9A9895',
    'editorWidget.background': '#202022', 'editorWidget.border': '#616163',
    'editorSuggestWidget.background': '#202022', 'editorSuggestWidget.border': '#616163',
    'editorHoverWidget.background': '#202022', 'editorHoverWidget.border': '#616163',
    'editor.findMatchBackground': '#A7A39B66', 'editor.findMatchHighlightBackground': '#A7A39B33',
  },
});

export default Editor;
