import React, { useRef, useState } from 'react';
import { Eye, FilePlus2, Pencil, Upload, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../../services/api';
import { getErrorDetail } from '../../services/errors';
import type { KnowledgeArticle } from '../../types';

interface ArticleEditorModalProps {
  /** The article being edited, or null to create a new one. */
  article: KnowledgeArticle | null;
  categories: string[];
  onClose: () => void;
  onSaved: (article: KnowledgeArticle, indexed: boolean) => void;
}

const MAX_UPLOAD_BYTES = 1024 * 1024;
const ACCEPTED_EXTENSIONS = ['.md', '.markdown', '.txt'];

/** Drop the leading `# Title` line: the title has its own field and is written back as the H1 on save. */
const splitTitle = (markdown: string): { title: string | null; body: string } => {
  const lines = markdown.replace(/^\uFEFF/, '').split(/\r?\n/);
  if (lines[0]?.startsWith('# ')) {
    return { title: lines[0].slice(2).trim(), body: lines.slice(1).join('\n').trim() };
  }
  return { title: null, body: markdown.trim() };
};

export const ArticleEditorModal: React.FC<ArticleEditorModalProps> = ({ article, categories, onClose, onSaved }) => {
  const isEditing = article !== null;
  const [title, setTitle] = useState(article?.title ?? '');
  const [category, setCategory] = useState(article?.category ?? 'General');
  const [content, setContent] = useState(() => (article ? splitTitle(article.content).body : ''));
  const [showPreview, setShowPreview] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');
  const fileInput = useRef<HTMLInputElement>(null);

  const handleFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError('');
    if (!ACCEPTED_EXTENSIONS.some(ext => file.name.toLowerCase().endsWith(ext))) {
      setError('Upload a Markdown (.md) or plain-text (.txt) file.');
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      setError('The file is larger than 1 MB.');
      return;
    }
    const { title: fileTitle, body } = splitTitle(await file.text());
    setContent(body);
    if (!title.trim()) {
      setTitle(fileTitle || file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' '));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsSaving(true);
    const payload = { title: title.trim(), category: category.trim() || 'General', content };
    try {
      const saved = isEditing
        ? await api.updateKnowledgeArticle(article.id, payload)
        : await api.createKnowledgeArticle(payload);
      onSaved(saved, saved.indexed);
    } catch (err) {
      setError(getErrorDetail(err, 'Could not save the document. Please try again.'));
    } finally {
      setIsSaving(false);
    }
  };

  const fieldClass =
    'w-full px-3 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-fade-in">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="article-editor-title"
        className="relative w-full max-w-3xl max-h-[90vh] flex flex-col bg-(--bg-card) border border-(--border-default) rounded-2xl shadow-2xl overflow-hidden animate-scale-up"
      >
        <div className="flex items-center justify-between p-5 sm:p-6 border-b border-(--border-default) shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary-500/10 text-primary-500 flex items-center justify-center">
              {isEditing ? <Pencil size={18} /> : <FilePlus2 size={20} />}
            </div>
            <div>
              <h3 id="article-editor-title" className="text-lg font-bold text-(--text-primary)">
                {isEditing ? 'Edit document' : 'New document'}
              </h3>
              <p className="text-xs text-(--text-secondary)">Visible to all employees as soon as you save</p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-lg text-(--text-tertiary) hover:text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col min-h-0 flex-1">
          <div className="p-5 sm:p-6 space-y-4 overflow-y-auto flex-1">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <label htmlFor="article-title" className="block text-sm font-medium text-(--text-primary) mb-1.5">Title</label>
                <input
                  id="article-title"
                  value={title}
                  onChange={e => setTitle(e.target.value)}
                  maxLength={120}
                  required
                  autoFocus={!isEditing}
                  placeholder="e.g. Parental Leave Policy"
                  className={fieldClass}
                />
              </div>
              <div>
                <label htmlFor="article-category" className="block text-sm font-medium text-(--text-primary) mb-1.5">Category</label>
                <input
                  id="article-category"
                  list="article-categories"
                  value={category}
                  onChange={e => setCategory(e.target.value)}
                  maxLength={40}
                  className={fieldClass}
                />
                <datalist id="article-categories">
                  {categories.map(c => <option key={c} value={c} />)}
                </datalist>
              </div>
            </div>

            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-1.5">
                <label htmlFor="article-content" className="text-sm font-medium text-(--text-primary)">
                  Content <span className="font-normal text-(--text-tertiary)">(Markdown)</span>
                </label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => fileInput.current?.click()}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-(--border-default) text-xs font-medium text-(--text-secondary) hover:text-(--text-primary) hover:bg-(--bg-secondary) transition-colors"
                  >
                    <Upload size={14} /> Upload file
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowPreview(p => !p)}
                    aria-pressed={showPreview}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                      showPreview
                        ? 'border-primary-500/40 bg-primary-500/10 text-primary-500'
                        : 'border-(--border-default) text-(--text-secondary) hover:text-(--text-primary) hover:bg-(--bg-secondary)'
                    }`}
                  >
                    <Eye size={14} /> Preview
                  </button>
                </div>
                <input
                  ref={fileInput}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(',')}
                  onChange={handleFile}
                  className="hidden"
                  aria-label="Upload a Markdown or text file"
                />
              </div>
              {showPreview ? (
                <div className="min-h-72 p-4 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) markdown-content">
                  {content.trim()
                    ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                    : <p className="text-(--text-tertiary)">Nothing to preview yet.</p>}
                </div>
              ) : (
                <textarea
                  id="article-content"
                  value={content}
                  onChange={e => setContent(e.target.value)}
                  required
                  rows={14}
                  placeholder={'## Overview\n\nWrite the document in Markdown, or upload a .md file.'}
                  className={`${fieldClass} min-h-72 font-mono text-[13px] leading-relaxed resize-y`}
                />
              )}
            </div>

            {error && <p role="alert" className="text-sm text-red-500">{error}</p>}
          </div>

          <div className="flex justify-end gap-3 p-5 sm:px-6 border-t border-(--border-default) shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-lg border border-(--border-default) text-(--text-primary) text-sm font-medium hover:bg-(--bg-secondary) transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSaving || !title.trim() || !content.trim()}
              className="px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors disabled:opacity-60"
            >
              {isSaving ? 'Saving...' : isEditing ? 'Save changes' : 'Publish document'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
