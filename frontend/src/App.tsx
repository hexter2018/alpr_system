/**
 * Main App Component
 * Contains routing and layout structure
 */

import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Layout, Menu, theme } from 'antd';
import {
  DashboardOutlined,
  UploadOutlined,
  CheckSquareOutlined,
  VideoCameraOutlined,
  DatabaseOutlined,
  BarChartOutlined,
} from '@ant-design/icons';

// Pages
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import VerificationPage from './pages/VerificationPage';
import StreamingPage from './pages/StreamingPage';
import MasterDataPage from './pages/MasterDataPage';

const { Header, Content, Sider } = Layout;

const App: React.FC = () => {
  const {
    token: { colorBgContainer },
  } = theme.useToken();

  return (
    <Router>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          breakpoint="lg"
          collapsedWidth="0"
          style={{
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
          }}
        >
          <div
            style={{
              height: 32,
              margin: 16,
              color: 'white',
              fontSize: 18,
              fontWeight: 'bold',
              textAlign: 'center',
            }}
          >
            Thai ALPR
          </div>
          <Menu
            theme="dark"
            mode="inline"
            defaultSelectedKeys={['1']}
            items={[
              {
                key: '1',
                icon: <DashboardOutlined />,
                label: <Link to="/">Dashboard</Link>,
              },
              {
                key: '2',
                icon: <UploadOutlined />,
                label: <Link to="/upload">Upload</Link>,
              },
              {
                key: '3',
                icon: <CheckSquareOutlined />,
                label: <Link to="/verification">Verification</Link>,
              },
              {
                key: '4',
                icon: <VideoCameraOutlined />,
                label: <Link to="/streaming">Streaming</Link>,
              },
              {
                key: '5',
                icon: <DatabaseOutlined />,
                label: <Link to="/master-data">Master Data</Link>,
              },
            ]}
          />
        </Sider>
        <Layout style={{ marginLeft: 200 }}>
          <Header
            style={{
              padding: '0 24px',
              background: colorBgContainer,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <h1 style={{ margin: 0 }}>Thai License Plate Recognition System</h1>
            <div>Admin</div>
          </Header>
          <Content style={{ margin: '24px 16px 0', overflow: 'initial' }}>
            <div
              style={{
                padding: 24,
                minHeight: 'calc(100vh - 112px)',
                background: colorBgContainer,
              }}
            >
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/upload" element={<UploadPage />} />
                <Route path="/verification" element={<VerificationPage />} />
                <Route path="/streaming" element={<StreamingPage />} />
                <Route path="/master-data" element={<MasterDataPage />} />
              </Routes>
            </div>
          </Content>
        </Layout>
      </Layout>
    </Router>
  );
};

export default App;
