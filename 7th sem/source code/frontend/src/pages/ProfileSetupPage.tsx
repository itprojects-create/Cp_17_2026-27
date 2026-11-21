import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  User, Mail, Code, Briefcase, Github, Globe, Clock,
  ChevronRight, ChevronLeft, Check, Save, Lock, Pencil, X, Wrench, FolderGit2
} from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '../services/api';
import { useAuth } from '../contexts/useAuth';

interface ProfileData {
  name: string;
  email: string;
  role: string;
  skills: string[];
  programming_languages: string[];
  tech_stack: string[];
  years_of_experience: number;
  current_projects: string;
  past_experience: string;
  github_username: string;
  preferred_tools: string[];
  timezone: string;
}

const roleFallback = ['Frontend', 'Backend', 'DevOps', 'ML', 'Fullstack'];
const languageFallback = ['JavaScript', 'TypeScript', 'Python', 'Go', 'Rust', 'Java', 'C++', 'C#', 'Ruby', 'PHP', 'Swift', 'Kotlin'];
const skillFallback = ['React', 'Vue', 'Angular', 'Node.js', 'Express', 'FastAPI', 'Django', 'Docker', 'Kubernetes', 'AWS', 'GCP', 'Azure', 'PostgreSQL', 'MongoDB', 'Redis', 'GraphQL', 'REST API', 'CI/CD', 'Git', 'Linux'];
const toolFallback = ['VS Code', 'WebStorm', 'Vim', 'Neovim', 'Emacs', 'Sublime Text', 'IntelliJ', 'PyCharm', 'Figma', 'Postman', 'Docker Desktop', 'iTerm2', 'Windows Terminal'];
const timezoneFallback = ['UTC+5:30 (IST)', 'UTC', 'UTC+0 (GMT)', 'UTC-8 (PST)', 'UTC-5 (EST)'];

const steps = [
  { title: 'Personal Info', icon: <User size={18} /> },
  { title: 'Role & Experience', icon: <Briefcase size={18} /> },
  { title: 'Skills & Tech', icon: <Code size={18} /> },
  { title: 'Preferences', icon: <Globe size={18} /> },
];

export const ProfileSetupPage: React.FC = () => {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [roleOptions, setRoleOptions] = useState<string[]>(roleFallback);
  const [languageOptions, setLanguageOptions] = useState<string[]>(languageFallback);
  const [skillOptions, setSkillOptions] = useState<string[]>(skillFallback);
  const [toolOptions, setToolOptions] = useState<string[]>(toolFallback);
  const [timezones, setTimezones] = useState<string[]>(timezoneFallback);
  const [data, setData] = useState<ProfileData>({
    name: '', email: '', role: '', skills: [], programming_languages: [],
    tech_stack: [], years_of_experience: 0, current_projects: '',
    past_experience: '', github_username: '', preferred_tools: [], timezone: '',
  });
  // The last saved profile: shown in view mode and restored when an edit is cancelled.
  const [saved, setSaved] = useState<ProfileData | null>(null);
  const { needsProfile, refreshUser } = useAuth();
  // A completed profile opens read-only; first-time setup goes straight to the form.
  const [isEditing, setIsEditing] = useState(needsProfile);

  React.useEffect(() => {
    const load = async () => {
      try {
        const [profile, options] = await Promise.all([api.getProfile(), api.getProfileOptions()]);
        setData(profile);
        setSaved(profile);
        setRoleOptions(options.roles?.length ? options.roles : roleFallback);
        setLanguageOptions(options.languages?.length ? options.languages : languageFallback);
        setSkillOptions(options.skills?.length ? options.skills : skillFallback);
        setToolOptions(options.tools?.length ? options.tools : toolFallback);
        setTimezones(options.timezones?.length ? options.timezones : timezoneFallback);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  const update = (field: keyof ProfileData, value: unknown) => {
    setData(prev => ({ ...prev, [field]: value }));
  };

  const toggleItem = (field: 'skills' | 'programming_languages' | 'tech_stack' | 'preferred_tools', item: string) => {
    setData(prev => ({
      ...prev,
      [field]: prev[field].includes(item) ? prev[field].filter(i => i !== item) : [...prev[field], item],
    }));
  };

  // Mirrors the backend rule (services/profile_status.py): saving without these would re-lock the app.
  const missingRequired = [
    ...(roleOptions.some(r => r.toLowerCase() === data.role.toLowerCase()) ? [] : ['role']),
    ...(data.tech_stack.length || data.programming_languages.length ? [] : ['a programming language or tech stack']),
  ];

  const startEditing = () => {
    setCurrentStep(0);
    setIsEditing(true);
  };

  const cancelEditing = () => {
    if (saved) setData(saved);
    setIsEditing(false);
  };

  const handleSaveDraft = async () => {
    try {
      setIsSaving(true);
      await api.updateProfile(data);
      toast.success('Draft saved to backend');
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSubmit = async () => {
    const firstTime = needsProfile;
    if (!firstTime && missingRequired.length) {
      toast.error(`Add ${missingRequired.join(' and ')} before saving.`);
      return;
    }
    try {
      setIsSaving(true);
      const result = await api.updateProfile(data);
      if (!result.profile_completed) {
        toast.error(`Please add your ${result.missing_fields.join(' and ')} to generate your checklist.`);
        return;
      }
      await refreshUser();
      setSaved(data);
      if (firstTime) {
        toast.success('Your personalized onboarding checklist is ready!');
        navigate('/app/checklist');
      } else {
        toast.success('Profile updated');
        setIsEditing(false);
      }
    } catch (e) {
      console.error(e);
      toast.error('Could not save your profile. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="p-8"><div className="skeleton h-56 w-full" /></div>;
  }

  const ChipSelector: React.FC<{ options: string[]; selected: string[]; field: 'skills' | 'programming_languages' | 'tech_stack' | 'preferred_tools' }> = ({ options, selected, field }) => (
    <div className="flex flex-wrap gap-2">
      {options.map(opt => (
        <button key={opt} type="button" onClick={() => toggleItem(field, opt)}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-all ${
            selected.includes(opt)
              ? 'bg-primary-500/10 border-primary-500/30 text-primary-500'
              : 'border-(--border-default) text-(--text-secondary) hover:border-primary-500/30'
          }`}>
          {selected.includes(opt) && <Check size={12} className="inline mr-1" />}
          {opt}
        </button>
      ))}
    </div>
  );

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-5 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Full Name *</label>
              <div className="relative">
                <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <input type="text" value={data.name} onChange={e => update('name', e.target.value)} placeholder="John Doe"
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Email *</label>
              <div className="relative">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <input type="email" value={data.email} onChange={e => update('email', e.target.value)} placeholder="dev@company.com"
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">GitHub Username</label>
              <div className="relative">
                <Github size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <input type="text" value={data.github_username} onChange={e => update('github_username', e.target.value)} placeholder="octocat"
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" />
              </div>
            </div>
          </div>
        );
      case 1:
        return (
          <div className="space-y-5 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-2">Role *</label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {roleOptions.map(role => (
                  <button key={role} type="button" onClick={() => update('role', role)}
                    className={`px-4 py-3 rounded-xl text-sm font-medium border transition-all text-center ${
                      data.role === role
                        ? 'bg-primary-500/10 border-primary-500 text-primary-500'
                        : 'border-(--border-default) text-(--text-secondary) hover:border-primary-500/30'
                    }`}>
                    {role}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Years of Experience</label>
              <input type="number" min={0} max={40} value={data.years_of_experience}
                onChange={e => update('years_of_experience', parseInt(e.target.value) || 0)}
                className="w-full px-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all" />
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Past Experience</label>
              <textarea value={data.past_experience} onChange={e => update('past_experience', e.target.value)} rows={3} placeholder="Brief description of your past experience..."
                className="w-full px-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all resize-none" />
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Current Projects</label>
              <textarea value={data.current_projects} onChange={e => update('current_projects', e.target.value)} rows={2} placeholder="What projects will you be joining?"
                className="w-full px-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all resize-none" />
            </div>
          </div>
        );
      case 2:
        return (
          <div className="space-y-6 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-2">Programming Languages</label>
              <ChipSelector options={languageOptions} selected={data.programming_languages} field="programming_languages" />
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-2">Skills & Frameworks</label>
              <ChipSelector options={skillOptions} selected={data.skills} field="skills" />
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-2">Tech Stack Familiarity</label>
              <ChipSelector options={skillOptions.slice(0, 10)} selected={data.tech_stack} field="tech_stack" />
            </div>
          </div>
        );
      case 3:
        return (
          <div className="space-y-6 animate-fade-in">
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-2">Preferred Tools</label>
              <ChipSelector options={toolOptions} selected={data.preferred_tools} field="preferred_tools" />
            </div>
            <div>
              <label className="block text-sm font-medium text-(--text-primary) mb-1.5">Timezone</label>
              <div className="relative">
                <Clock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-(--text-tertiary)" />
                <select value={data.timezone} onChange={e => update('timezone', e.target.value)}
                  className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-(--border-default) bg-(--bg-secondary) text-(--text-primary) text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 transition-all appearance-none">
                  <option value="">Select timezone</option>
                  {timezones.map(tz => <option key={tz} value={tz}>{tz}</option>)}
                </select>
              </div>
            </div>
          </div>
        );
    }
  };

  if (!isEditing) {
    const profile = saved ?? data;
    const Field: React.FC<{ label: string; value?: React.ReactNode }> = ({ label, value }) => (
      <div>
        <dt className="text-xs font-medium uppercase tracking-wide text-(--text-tertiary)">{label}</dt>
        <dd className="mt-1 text-sm text-(--text-primary) whitespace-pre-wrap break-words">{value || <span className="text-(--text-tertiary)">Not provided</span>}</dd>
      </div>
    );
    const Chips: React.FC<{ label: string; items: string[] }> = ({ label, items }) => (
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-(--text-tertiary) mb-2">{label}</p>
        {items.length ? (
          <div className="flex flex-wrap gap-2">
            {items.map(item => (
              <span key={item} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-primary-500/10 text-primary-600 dark:text-primary-400 border border-primary-500/20">{item}</span>
            ))}
          </div>
        ) : <p className="text-sm text-(--text-tertiary)">None selected</p>}
      </div>
    );
    const Section: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode }> = ({ title, icon, children }) => (
      <section className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 sm:p-6">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-(--text-primary) mb-5">{icon}{title}</h2>
        {children}
      </section>
    );

    return (
      <div className="px-4 py-5 sm:p-6 md:p-8 max-w-4xl mx-auto animate-fade-in">
        <div className="flex items-start justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-(--text-primary)">My Profile</h1>
            <p className="text-(--text-secondary) mt-1">Your onboarding plan is personalized from these details</p>
          </div>
          <button onClick={startEditing}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors shadow-sm shrink-0">
            <Pencil size={16} /> Edit
          </button>
        </div>

        <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-5 sm:p-6 mb-6 flex flex-col sm:flex-row sm:items-center gap-4">
          <div className="w-16 h-16 shrink-0 rounded-full bg-linear-to-br from-primary-500 to-accent-500 text-white flex items-center justify-center text-2xl font-bold">
            {(profile.name || profile.email || '?').charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="text-lg font-bold text-(--text-primary) truncate">{profile.name || 'Unnamed developer'}</p>
            <p className="text-sm text-(--text-secondary)">
              {profile.role || 'No role'} developer · {profile.years_of_experience} {profile.years_of_experience === 1 ? 'year' : 'years'} of experience
            </p>
            <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-sm text-(--text-secondary)">
              <span className="inline-flex items-center gap-1.5 min-w-0"><Mail size={14} className="shrink-0" /><span className="truncate">{profile.email || 'No email'}</span></span>
              {profile.github_username && <span className="inline-flex items-center gap-1.5"><Github size={14} />{profile.github_username}</span>}
              {profile.timezone && <span className="inline-flex items-center gap-1.5"><Clock size={14} />{profile.timezone}</span>}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Section title="Role & Experience" icon={<Briefcase size={16} className="text-primary-500" />}>
            <dl className="space-y-4">
              <Field label="Role" value={profile.role} />
              <Field label="Years of experience" value={String(profile.years_of_experience)} />
              <Field label="Past experience" value={profile.past_experience} />
            </dl>
          </Section>
          <Section title="Current Projects" icon={<FolderGit2 size={16} className="text-primary-500" />}>
            <dl><Field label="Projects you're joining" value={profile.current_projects} /></dl>
          </Section>
          <Section title="Skills & Tech" icon={<Code size={16} className="text-primary-500" />}>
            <div className="space-y-5">
              <Chips label="Programming languages" items={profile.programming_languages} />
              <Chips label="Skills & frameworks" items={profile.skills} />
              <Chips label="Tech stack familiarity" items={profile.tech_stack} />
            </div>
          </Section>
          <Section title="Preferences" icon={<Wrench size={16} className="text-primary-500" />}>
            <div className="space-y-5">
              <Chips label="Preferred tools" items={profile.preferred_tools} />
              <dl><Field label="Timezone" value={profile.timezone} /></dl>
            </div>
          </Section>
        </div>
      </div>
    );
  }

  return (
    <div className="px-4 py-5 sm:p-6 md:p-8 max-w-3xl mx-auto animate-fade-in">
      <div className="flex items-start justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-(--text-primary)">{needsProfile ? 'Developer Profile Setup' : 'Edit Profile'}</h1>
          <p className="text-(--text-secondary) mt-1">
            {needsProfile ? 'Complete your profile to personalize your onboarding experience' : 'Update your details, then save your changes'}
          </p>
        </div>
        {!needsProfile && (
          <button onClick={cancelEditing} disabled={isSaving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-(--border-default) text-sm font-medium text-(--text-primary) hover:bg-(--bg-secondary) transition-colors shrink-0">
            <X size={16} /> Cancel
          </button>
        )}
      </div>

      {!needsProfile && (
        <p className="mb-6 text-sm text-(--text-secondary) p-3 rounded-lg bg-(--bg-secondary) border border-(--border-default)">
          Changing your role or tech stack updates your onboarding plan. Tasks you've already started or completed are kept.
        </p>
      )}

      {needsProfile && (
        <div role="status" className="flex items-start gap-3 mb-6 p-4 rounded-xl border border-primary-500/25 bg-primary-500/5">
          <Lock size={18} className="text-primary-500 shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="font-semibold text-(--text-primary)">Finish your profile to start onboarding</p>
            <p className="text-(--text-secondary) mt-0.5">
              Your onboarding checklist is generated from your <strong>role</strong> and <strong>tech stack</strong>.
              The rest of the app unlocks as soon as you complete setup.
            </p>
          </div>
        </div>
      )}

      {/* Progress Steps */}
      <div className="flex items-center mb-8 overflow-x-auto pb-2">
        {steps.map((step, i) => (
          <React.Fragment key={step.title}>
            <button
              onClick={() => setCurrentStep(i)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                i === currentStep ? 'bg-primary-500/10 text-primary-500' :
                i < currentStep ? 'text-green-500' : 'text-(--text-tertiary)'
              }`}
            >
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs border-2 ${
                i === currentStep ? 'border-primary-500 bg-primary-500/10' :
                i < currentStep ? 'border-green-500 bg-green-500/10' : 'border-(--border-default)'
              }`}>
                {i < currentStep ? <Check size={14} /> : i + 1}
              </div>
              <span className="hidden sm:inline">{step.title}</span>
            </button>
            {i < steps.length - 1 && (
              <div className={`w-8 h-0.5 mx-1 rounded ${i < currentStep ? 'bg-green-500' : 'bg-(--border-default)'}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Form Card */}
      <div className="bg-(--bg-card) border border-(--border-default) rounded-xl p-6 md:p-8">
        <div className="flex items-center gap-2 mb-6">
          {steps[currentStep].icon}
          <h2 className="text-lg font-semibold text-(--text-primary)">{steps[currentStep].title}</h2>
        </div>
        {renderStep()}
      </div>

      {/* Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3 mt-6">
        {needsProfile ? (
          <button disabled={isSaving} onClick={handleSaveDraft} className="flex items-center gap-2 px-4 py-2 rounded-lg border border-(--border-default) text-sm font-medium text-(--text-secondary) hover:bg-(--bg-secondary) transition-colors disabled:opacity-50">
            <Save size={16} /> Save Draft
          </button>
        ) : (
          // Editing a complete profile can be saved from any step; incomplete edits are blocked.
          <div className="flex flex-col">
            <button disabled={isSaving || missingRequired.length > 0} onClick={handleSubmit}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
              <Save size={16} /> {isSaving ? 'Saving...' : 'Save changes'}
            </button>
            {missingRequired.length > 0 && (
              <span className="text-xs text-red-500 mt-1">Add {missingRequired.join(' and ')} to save.</span>
            )}
          </div>
        )}
        <div className="flex items-center gap-3">
          {currentStep > 0 && (
            <button onClick={() => setCurrentStep(s => s - 1)} className="flex items-center gap-1 px-4 py-2 rounded-lg border border-(--border-default) text-sm font-medium text-(--text-secondary) hover:bg-(--bg-secondary) transition-colors">
              <ChevronLeft size={16} /> Back
            </button>
          )}
          {currentStep < steps.length - 1 ? (
            <button onClick={() => setCurrentStep(s => s + 1)} className="flex items-center gap-1 px-4 py-2.5 rounded-lg bg-primary-500 text-white text-sm font-medium hover:bg-primary-600 transition-colors">
              Next <ChevronRight size={16} />
            </button>
          ) : !needsProfile ? null : (
            <button disabled={isSaving} onClick={handleSubmit} className="flex items-center gap-1 px-6 py-2.5 rounded-lg bg-linear-to-r from-primary-500 to-accent-500 text-white text-sm font-medium hover:from-primary-600 hover:to-accent-600 transition-all shadow-lg shadow-primary-500/20 disabled:opacity-50">
              {isSaving ? 'Saving...' : 'Complete Setup'} <Check size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
