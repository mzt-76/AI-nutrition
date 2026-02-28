import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { CopilotKitProvider } from "@copilotkit/react-core/v2"
import { HttpAgent } from "@ag-ui/client"
import './index.css'
import App from './App.tsx'
import A2UITestPage from './A2UITestPage.tsx'
import NewsComponentsTestPage from './pages/NewsComponentsTestPage.tsx'
import TestPeopleComponents from './pages/TestPeopleComponents.tsx'
import SummaryComponentsTestPage from './pages/SummaryComponentsTestPage.tsx'
import MediaComponentsTest from './pages/MediaComponentsTest.tsx'
import DataComponentsTest from './pages/DataComponentsTest.tsx'
import ResourceTest from './pages/ResourceTest.tsx'
import A2UIValidatorTest from './pages/A2UIValidatorTest.tsx'
import ComponentShowcase from './pages/ComponentShowcase.tsx'

// Use test pages based on query params (check specific tests first to avoid conflicts)
const USE_SHOWCASE = window.location.search.includes('showcase');
const USE_VALIDATOR_TEST_PAGE = window.location.search.includes('validator-test');
const USE_RESOURCE_TEST_PAGE = window.location.search.includes('resource-test');
const USE_DATA_TEST_PAGE = window.location.search.includes('data-test');
const USE_MEDIA_TEST_PAGE = window.location.search.includes('media-test');
const USE_SUMMARY_TEST_PAGE = window.location.search.includes('summary-test');
const USE_PEOPLE_TEST_PAGE = window.location.search.includes('people-test');
const USE_NEWS_TEST_PAGE = window.location.search.includes('news-test');
const USE_TEST_PAGE = window.location.search === '?test' || window.location.search.startsWith('?test&');

// Backend URL for AG-UI / CopilotKit connection
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

console.log('AG-UI Backend URL:', BACKEND_URL)

// Create HttpAgent pointing to our AG-UI endpoint
// The backend serves AG-UI at root path
const dashboardAgent = new HttpAgent({
  url: BACKEND_URL,
  agentId: "dashboard_agent",
})

// Determine which component to render
function getAppComponent() {
  if (USE_SHOWCASE) return <ComponentShowcase />;
  if (USE_VALIDATOR_TEST_PAGE) return <A2UIValidatorTest />;
  if (USE_RESOURCE_TEST_PAGE) return <ResourceTest />;
  if (USE_DATA_TEST_PAGE) return <DataComponentsTest />;
  if (USE_MEDIA_TEST_PAGE) return <MediaComponentsTest />;
  if (USE_SUMMARY_TEST_PAGE) return <SummaryComponentsTestPage />;
  if (USE_PEOPLE_TEST_PAGE) return <TestPeopleComponents />;
  if (USE_NEWS_TEST_PAGE) return <NewsComponentsTestPage />;
  if (USE_TEST_PAGE) return <A2UITestPage />;
  return <App />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <CopilotKitProvider
      agents__unsafe_dev_only={{
        dashboard_agent: dashboardAgent,
      }}
    >
      {getAppComponent()}
    </CopilotKitProvider>
  </StrictMode>,
)
