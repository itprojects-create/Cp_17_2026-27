import React, { useState } from 'react';
import { Search, BookOpen, FileText, Code, Shield, ExternalLink, Quote, SearchX, Loader2, Plus, Pencil, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, type KnowledgeAnswer } from '../services/api';
import { getErrorDetail } from '../services/errors';
import { useAuth } from '../contexts/useAuth';
import { ArticleEditorModal } from '../components/knowledge/ArticleEditorModal';
import type { KnowledgeArticle } from '../types';

const categoryIcons: Record<string, React.ReactNode> = {
  'Getting Started': <BookOpen size={18} />,
  'Coding Standards': <Code size={18} />,
  'Architecture': <FileText size={18} />,
  'Security': <Shield size={18} />,
};

export const KnowledgeBasePage: React.FC = () => {
  const [articles, setArticles] = useState<KnowledgeArticle[]>([]);
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [selectedArticle, setSelectedArticle] = useState<KnowledgeArticle | null>(null);
  const [aiResult, setAiResult] = useState<KnowledgeAnswer | null>(null);
  const [askError, setAskError] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const { isAdmin } = useAuth();
  // undefined: editor closed; null: creating a new document; article: editing it.
  const [editing, setEditing] = useState<KnowledgeArticle | null | undefined>(undefined);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notice, setNotice] = useState<{ tone: 'success' | 'warning' | 'error'; text: string } | null>(null);

  React.useEffect(() => {
    const load = async () => {
      try {
        const data = await api.getKnowledgeArticles();
        setArticles(data);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  const categories = [...new Set(articles.map(a => a.category))];

  const filtered = articles.filter(a => {
    if (selectedCategory && a.category !== selectedCategory) return false;
    if (search) {
      const q = search.toLowerCase();
      return a.title.toLowerCase().includes(q) || a.tags.some(t => t.includes(q)) || a.content.toLowerCase().includes(q);
    }
    return true;
  });

  const handleAskAI = async () => {
    if (!search.trim() || isAsking) return;
    setIsAsking(true);
    setAiResult(null);
    setAskError('');
    try {
      setAiResult(await api.askKnowledge(search));
    } catch (e) {
      console.error(e);
      setAskError('I could not fetch an answer right now. Please try again.');
    } finally {
      setIsAsking(false);
    }
  };

  const openArticle = (article: KnowledgeArticle | null) => {
    setSelectedArticle(article);
    setConfirmingDelete(false);
  };

  const handleSaved = (saved: KnowledgeArticle, indexed: boolean) => {
    const isNew = !articles.some(a => a.id === saved.id);
    setArticles(prev => isNew ? [...prev, saved].sort((a, b) => a.id.localeCompare(b.id)) : prev.map(a => a.id === saved.id ? saved : a));
    setEditing(undefined);
    setSelectedCategory(null);
    openArticle(saved);
    setNotice(indexed
      ? { tone: 'success', text: isNew ? 'Document published. Employees can now see it.' : 'Changes saved. Employees now see the updated document.' }
      : { tone: 'warning', text: 'Saved, but search indexing failed. Employees can open the document, but search may not find it until the server re-indexes.' });
  };

  const handleDelete = async () => {
    if (!selectedArticle) return;
    setIsDeleting(true);
    try {
      await api.deleteKnowledgeArticle(selectedArticle.id);
      setArticles(prev => prev.filter(a => a.id !== selectedArticle.id));
      setNotice({ tone: 'success', text: `"${selectedArticle.title}" was deleted.` });
      openArticle(null);
    } catch (e) {
      setNotice({ tone: 'error', text: getErrorDetail(e, 'Could not delete the document. Please try again.') });
      setConfirmingDelete(false);
    } finally {
      setIsDeleting(false);
    }
  };

  const openCitation = (articleId: string) => {
    const article = articles.find(a => a.id === articleId);
    if (article) {
      setSelectedCategory(null);
      openArticle(article);
    }
  };

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-7xl mx-auto animate-fade-in">
      <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-(--text-primary)">Knowledge Base</h1>
          <p className="text-(--text-secondary) mt-1">Search company documentation and policies</p>
        </div>
        {isAdmin && (
          <button
            onClick={() => setEditing(null)}
            className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors shadow-sm whitespace-nowrap"
          >
            <Plus size={16} /> New document
          </button>
        )}
      </div>

      {notice && (
        <div
          role="status"
          className={`mb-6 flex items-start justify-between gap-3 p-3 rounded-lg border text-sm ${
            notice.tone === 'success'
              ? 'bg-green-500/10 border-green-500/20 text-green-700 dark:text-green-400'
              : notice.tone === 'warning'
                ? 'bg-amber-500/10 border-amber-500/20 text-amber-700 dark:text-amber-400'
                : 'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400'
          }`}
        >
          <span>{notice.text}</span>
          <button onClick={() => setNotice(null)} aria-label="Dismiss" className="shrink-0 opacity-70 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Search */}
      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-4 sm:p-6 mb-8">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
            <input type="text" value={search} onChange={e => setSearch(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleAskAI()}
              placeholder="Search documentation or ask a question..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-(--border-default) bg-(--bg-secondary) text-sm text-(--text-primary) focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" />
          </div>
          <button onClick={handleAskAI} disabled={isAsking || !search.trim()}
            aria-label={isAsking ? 'Searching' : 'Search'} title="Search"
            className="flex items-center justify-center px-4 py-3 rounded-xl bg-linear-to-r from-primary-500 to-accent-500 text-white hover:from-primary-600 hover:to-accent-600 transition-all disabled:opacity-50 cursor-pointer disabled:cursor-not-allowed">
            {isAsking ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
          </button>
        </div>
        {isAsking && (
          <div className="mt-4 p-4 rounded-xl border border-(--border-default) space-y-2" aria-live="polite">
            <div className="skeleton h-4 w-1/3" />
            <div className="skeleton h-4 w-full" />
            <div className="skeleton h-4 w-5/6" />
          </div>
        )}
        {askError && !isAsking && (
          <p className="mt-4 text-sm text-red-500" role="alert">{askError}</p>
        )}
        {aiResult && !isAsking && (
          <div
            className={`mt-4 p-4 rounded-xl border animate-fade-in ${
              aiResult.mode === 'ai'
                ? 'bg-primary-500/5 border-primary-500/15'
                : aiResult.mode === 'excerpts'
                  ? 'bg-amber-500/5 border-amber-500/20'
                  : 'bg-(--bg-secondary) border-(--border-default)'
            }`}
            aria-live="polite"
          >
            <div className="flex items-center gap-2 mb-2">
              {aiResult.mode === 'ai' && <Search size={16} className="text-primary-500" />}
              {aiResult.mode === 'excerpts' && <Quote size={16} className="text-amber-500" />}
              {aiResult.mode === 'none' && <SearchX size={16} className="text-(--text-tertiary)" />}
              <span className={`text-sm font-semibold ${
                aiResult.mode === 'ai' ? 'text-primary-500' : aiResult.mode === 'excerpts' ? 'text-amber-600 dark:text-amber-400' : 'text-(--text-secondary)'
              }`}>
                {aiResult.mode === 'ai' ? 'Answer' : aiResult.mode === 'excerpts' ? 'Relevant excerpts' : 'No answer found'}
              </span>
            </div>
            {aiResult.mode === 'excerpts' && (
              <p className="text-xs text-(--text-secondary) mb-3">
                A summarized answer isn't available right now, so these are the matching passages from the documentation.
              </p>
            )}
            <div className="text-sm text-(--text-primary) markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{aiResult.answer}</ReactMarkdown>
            </div>
            {aiResult.citations.length > 0 && (
              <div className="mt-4 pt-3 border-t border-(--border-default)">
                <p className="text-xs font-medium text-(--text-tertiary) mb-2">Sources</p>
                <div className="flex flex-wrap gap-2">
                  {aiResult.citations.map(c => (
                    <button
                      key={`${c.source}-${c.section ?? ''}`}
                      onClick={() => openCitation(c.article_id)}
                      className="inline-flex items-center gap-1.5 max-w-full px-2.5 py-1 rounded-lg text-xs bg-(--bg-card) border border-(--border-default) text-(--text-secondary) hover:text-primary-500 hover:border-primary-500/40 transition-colors cursor-pointer"
                      title={c.section ? `${c.source} › ${c.section}` : c.source}
                    >
                      <FileText size={12} className="shrink-0" />
                      <span className="truncate">
                        {c.article_id.replace(/_/g, ' ')}
                        {c.section && <span className="text-(--text-tertiary)"> › {c.section}</span>}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-6">
        {/* Categories Sidebar */}
        <div className="hidden md:block w-56 shrink-0">
          <h3 className="text-sm font-semibold text-(--text-primary) mb-3">Categories</h3>
          <button onClick={() => { setSelectedCategory(null); openArticle(null); }}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors mb-1 ${!selectedCategory ? 'bg-primary-500/10 text-primary-500 font-medium' : 'text-(--text-secondary) hover:bg-(--bg-secondary)'}`}>
            All Articles
          </button>
          {categories.map(cat => (
            <button key={cat} onClick={() => { setSelectedCategory(cat); openArticle(null); }}
              className={`w-full flex items-center gap-2 text-left px-3 py-2 rounded-lg text-sm transition-colors mb-1 ${selectedCategory === cat ? 'bg-primary-500/10 text-primary-500 font-medium' : 'text-(--text-secondary) hover:bg-(--bg-secondary)'}`}>
              {categoryIcons[cat] || <FileText size={18} />}
              {cat}
            </button>
          ))}
        </div>

        {/* Articles Grid */}
        <div className="flex-1">
          {isLoading ? (
            <div className="text-center py-16">
              <BookOpen size={48} className="text-(--text-tertiary) mx-auto mb-3" />
              <p className="text-(--text-primary) font-medium">Loading knowledge base...</p>
            </div>
          ) : selectedArticle ? (
            <div className="animate-fade-in">
              <button onClick={() => openArticle(null)}
                className="text-sm text-primary-500 hover:text-primary-400 mb-4 flex items-center gap-1">
                ← Back to articles
              </button>
              <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 sm:p-8">
                <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-primary-500/10 text-primary-500 font-medium">{selectedArticle.category}</span>
                  {isAdmin && (
                    confirmingDelete ? (
                      <div className="flex items-center gap-2 text-sm">
                        <span className="text-(--text-secondary)">Delete for everyone?</span>
                        <button onClick={handleDelete} disabled={isDeleting}
                          className="px-3 py-1.5 rounded-lg bg-red-500 text-white text-xs font-medium hover:bg-red-600 transition-colors disabled:opacity-60">
                          {isDeleting ? 'Deleting...' : 'Delete'}
                        </button>
                        <button onClick={() => setConfirmingDelete(false)} disabled={isDeleting}
                          className="px-3 py-1.5 rounded-lg border border-(--border-default) text-(--text-primary) text-xs font-medium hover:bg-(--bg-secondary) transition-colors">
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <button onClick={() => setEditing(selectedArticle)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-(--border-default) text-(--text-primary) text-xs font-medium hover:bg-(--bg-secondary) transition-colors">
                          <Pencil size={14} /> Edit
                        </button>
                        <button onClick={() => setConfirmingDelete(true)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-500/30 text-red-500 text-xs font-medium hover:bg-red-500/10 transition-colors">
                          <Trash2 size={14} /> Delete
                        </button>
                      </div>
                    )
                  )}
                </div>
                <h2 className="text-xl font-bold text-(--text-primary) mt-2 mb-1">{selectedArticle.title}</h2>
                <p className="text-xs text-(--text-tertiary) mb-6">
                  Last updated {new Date(Number(selectedArticle.updated_at) * 1000).toLocaleDateString()}
                  {selectedArticle.updated_by && <> by {selectedArticle.updated_by}</>}
                </p>
                <div className="text-sm text-(--text-primary) markdown-content [&>h1:first-child]:hidden">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{selectedArticle.content}</ReactMarkdown>
                </div>
                <div className="mt-6 pt-4 border-t border-(--border-default) flex flex-wrap gap-2">
                  {selectedArticle.tags.map(tag => (
                    <span key={tag} className="text-xs px-2 py-1 rounded-full bg-(--bg-tertiary) text-(--text-secondary)">#{tag}</span>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filtered.map(article => (
                <button key={article.id} onClick={() => openArticle(article)}
                  className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 text-left hover:shadow-md hover:border-primary-500/20 transition-all group">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-primary-500/10 text-primary-500 font-medium">{article.category}</span>
                    <ExternalLink size={14} className="text-(--text-tertiary) group-hover:text-primary-500 transition-colors" />
                  </div>
                  <h3 className="text-sm font-semibold text-(--text-primary) group-hover:text-primary-500 transition-colors mb-2">{article.title}</h3>
                  <p className="text-xs text-(--text-secondary) line-clamp-2">{article.content.replace(/[#*`]/g, '').slice(0, 120)}...</p>
                  <div className="mt-3 flex gap-1.5">
                    {article.tags.slice(0, 3).map(tag => (
                      <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded bg-(--bg-tertiary) text-(--text-tertiary)">#{tag}</span>
                    ))}
                  </div>
                </button>
              ))}
              {filtered.length === 0 && (
                <div className="col-span-2 text-center py-16">
                  <BookOpen size={48} className="text-(--text-tertiary) mx-auto mb-3" />
                  <p className="text-(--text-primary) font-medium">No articles found</p>
                  <p className="text-sm text-(--text-secondary)">Try a different search term</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {editing !== undefined && (
        <ArticleEditorModal
          article={editing}
          categories={categories}
          onClose={() => setEditing(undefined)}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
};
