// ── Styles (bundled CSS — side-effect import so bundler includes CSS) ──
import './styles/index.css';

// ── Primitives ────────────────────────────────────────────────────
export { Button, ButtonRow } from './components/Button/Button';
export type { ButtonProps, ButtonVariant } from './components/Button/Button';

export { Tabs } from './components/Tabs/Tabs';
export type { TabsProps, TabItem } from './components/Tabs/Tabs';

export { FilterTabs } from './components/FilterTabs/FilterTabs';
export type { FilterTabsProps, FilterTab } from './components/FilterTabs/FilterTabs';

export { Card } from './components/Card/Card';
export type { CardProps } from './components/Card/Card';

export { SectionHead } from './components/SectionHead/SectionHead';
export type { SectionHeadProps } from './components/SectionHead/SectionHead';

export { InfoCard } from './components/InfoCard/InfoCard';
export type { InfoCardProps } from './components/InfoCard/InfoCard';

export { Field } from './components/Field/Field';
export type { FieldProps } from './components/Field/Field';

export { Input, Textarea } from './components/Input/Input';
export type { InputProps, TextareaProps } from './components/Input/Input';

export { Select } from './components/Select/Select';
export type { SelectProps, SelectOption } from './components/Select/Select';

export { Checkbox } from './components/Checkbox/Checkbox';
export type { CheckboxProps } from './components/Checkbox/Checkbox';

export { Brand } from './components/Brand/Brand';
export type { BrandProps } from './components/Brand/Brand';

export { StatusDot } from './components/StatusDot/StatusDot';
export type { StatusDotProps } from './components/StatusDot/StatusDot';

export { ThemeToggle } from './components/ThemeToggle/ThemeToggle';
export type { ThemeToggleProps } from './components/ThemeToggle/ThemeToggle';

export { Msg } from './components/Msg/Msg';
export type { MsgProps, MsgVariant } from './components/Msg/Msg';

export { Pill } from './components/Pill/Pill';
export type { PillProps, PillVariant } from './components/Pill/Pill';

export { Empty } from './components/Empty/Empty';
export type { EmptyProps } from './components/Empty/Empty';

export { QualityBadge } from './components/QualityBadge/QualityBadge';
export type { QualityBadgeProps } from './components/QualityBadge/QualityBadge';

export { ExplicitTag } from './components/ExplicitTag/ExplicitTag';

export {
  TrackIcon, AlbumIcon, DiscographyIcon, PlaylistIcon,
  ExpandAlbumsIcon, ExpandDiscographiesIcon, ExplicitUpgradeIcon,
  RetagLibraryIcon, FetchLyricsIcon, FetchArtIcon,
  DownloadIcon, RefreshIcon, CloseIcon, SearchIcon,
  TYPE_ICONS, TYPE_LABELS,
} from './components/Icon/Icon';

// ── Domain components ─────────────────────────────────────────────
export { ModeButton, MODE_DESCS } from './components/ModeButton/ModeButton';
export type { ModeButtonProps } from './components/ModeButton/ModeButton';

export { ModeGrid } from './components/ModeGrid/ModeGrid';
export type { ModeGridProps } from './components/ModeGrid/ModeGrid';

export { JobCard } from './components/JobCard/JobCard';
export type { JobCardProps } from './components/JobCard/JobCard';

export { JobsList } from './components/JobsList/JobsList';
export type { JobsListProps } from './components/JobsList/JobsList';

export { StatCard, StatCards } from './components/StatCard/StatCard';
export type { StatCardProps, StatCardsProps } from './components/StatCard/StatCard';

export { LibraryCard } from './components/LibraryCard/LibraryCard';
export type { LibraryCardProps } from './components/LibraryCard/LibraryCard';

export { LibraryGrid } from './components/LibraryGrid/LibraryGrid';
export type { LibraryGridProps } from './components/LibraryGrid/LibraryGrid';

export { SearchResult } from './components/SearchResult/SearchResult';
export type { SearchResultProps } from './components/SearchResult/SearchResult';

export { SearchResults } from './components/SearchResults/SearchResults';
export type { SearchResultsProps } from './components/SearchResults/SearchResults';

export { Modal } from './components/Modal/Modal';
export type { ModalProps } from './components/Modal/Modal';

export { LogViewer } from './components/LogViewer/LogViewer';
export type { LogViewerProps } from './components/LogViewer/LogViewer';

export { AlbumDetail } from './components/AlbumDetail/AlbumDetail';
export type { AlbumDetailProps } from './components/AlbumDetail/AlbumDetail';

// ── Screens ───────────────────────────────────────────────────────
export { AppShell } from './screens/AppShell/AppShell';
export type { AppShellProps } from './screens/AppShell/AppShell';

export { AddScreen } from './screens/AddScreen/AddScreen';
export type { AddScreenProps } from './screens/AddScreen/AddScreen';

export { JobsScreen } from './screens/JobsScreen/JobsScreen';
export type { JobsScreenProps } from './screens/JobsScreen/JobsScreen';

export { LibraryScreen } from './screens/LibraryScreen/LibraryScreen';
export type { LibraryScreenProps, LibraryStats } from './screens/LibraryScreen/LibraryScreen';

export { SettingsScreen } from './screens/SettingsScreen/SettingsScreen';
export type { SettingsScreenProps, Settings } from './screens/SettingsScreen/SettingsScreen';

// ── Types (re-export fixtures for consumers) ──────────────────────
export type { Job, JobStatus, JobType } from './_fixtures/jobs';
export type { Album, AlbumDetail as AlbumDetailData, Track } from './_fixtures/library';
export type { SearchResultItem } from './_fixtures/search';
