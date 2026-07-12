import { createHashRouter } from 'react-router-dom';
import { Home } from './pages/Home';
import { Workbench } from './pages/Workbench';
import { RagPlaceholder } from './pages/RagPlaceholder';
import Settings from './pages/Settings';
import { SeededResearch } from './pages/SeededResearch';
import { Layout } from './components/Layout';

export const router = createHashRouter([
  {
    path: '/',
    element: <Layout><Home /></Layout>,
  },
  {
    path: '/workbench',
    element: <Layout><Workbench /></Layout>,
  },
  {
    path: '/workbench/:caseId',
    element: <Layout><Workbench /></Layout>,
  },
  {
    path: '/seeded-research',
    element: <Layout><SeededResearch /></Layout>,
  },
  {
    path: '/rag',
    element: <Layout><RagPlaceholder /></Layout>,
  },
  {
    path: '/settings',
    element: <Layout><Settings /></Layout>,
  },
]);
