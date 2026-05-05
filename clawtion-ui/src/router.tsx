import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import NoteListPage from '@/pages/NoteListPage'
import NoteCreatePage from '@/pages/NoteCreatePage'
import NoteEditPage from '@/pages/NoteEditPage'
import SearchPage from '@/pages/SearchPage'
import ChunkDetailPage from '@/pages/ChunkDetailPage'
import SettingsPage from '@/pages/SettingsPage'
import QueuePage from '@/pages/QueuePage'
import TrashPage from '@/pages/TrashPage'
import SystemPage from '@/pages/SystemPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      { index: true, element: <NoteListPage /> },
      { path: 'notes', element: <NoteListPage /> },
      { path: 'notes/new', element: <NoteCreatePage /> },
      { path: 'notes/:documentId', element: <NoteEditPage /> },
      { path: 'search', element: <SearchPage /> },
      { path: 'search/chunks/:chunkId', element: <ChunkDetailPage /> },
      { path: 'settings', element: <SettingsPage /> },
      { path: 'queue', element: <QueuePage /> },
      { path: 'trash', element: <TrashPage /> },
      { path: 'system', element: <SystemPage /> },
    ],
  },
])
