/**
 * Enhanced Dashboard Page
 * Shows system overview, multi-camera status, and export options
 */

import React, { useState, useEffect } from 'react';
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Button,
  Select,
  DatePicker,
  Space,
  Tag,
  Progress,
  Modal,
  message,
} from 'antd';
import {
  DownloadOutlined,
  FileExcelOutlined,
  FilePdfOutlined,
  CameraOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { Line, Bar } from 'recharts';
import { api } from '../services/api';
import dayjs from 'dayjs';

const { RangePicker } = DatePicker;
const { Option } = Select;

interface DashboardStats {
  total_records: number;
  today_records: number;
  alpr_count: number;
  mlpr_count: number;
  pending_count: number;
  accuracy_rate: number;
  avg_confidence: number;
  registered_rate: number;
}

interface CameraStatus {
  camera_id: number;
  camera_name: string;
  status: string;
  frame_count?: number;
  triggered_tracks?: number;
}

const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<DashboardStats>({
    total_records: 0,
    today_records: 0,
    alpr_count: 0,
    mlpr_count: 0,
    pending_count: 0,
    accuracy_rate: 0,
    avg_confidence: 0,
    registered_rate: 0,
  });

  const [cameras, setCameras] = useState<CameraStatus[]>([]);
  const [dailyTrend, setDailyTrend] = useState<any[]>([]);
  const [exportModalVisible, setExportModalVisible] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportConfig, setExportConfig] = useState({
    format: 'excel',
    reportType: 'detailed',
    dateRange: null as [dayjs.Dayjs, dayjs.Dayjs] | null,
  });

  useEffect(() => {
    fetchDashboardData();
    fetchCameraStatus();
    fetchDailyTrend();

    // Refresh every 30 seconds
    const interval = setInterval(() => {
      fetchDashboardData();
      fetchCameraStatus();
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      const response = await api.analytics.getDashboard();
      setStats(response.data);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
    }
  };

  const fetchCameraStatus = async () => {
    try {
      const response = await api.streaming.getActiveStreams();
      setCameras(response.data);
    } catch (error) {
      console.error('Failed to fetch camera status:', error);
    }
  };

  const fetchDailyTrend = async () => {
    try {
      const response = await api.analytics.getDailyTrend(7);
      const chartData = response.data.dates.map((date: string, index: number) => ({
        date,
        total: response.data.total[index],
        alpr: response.data.alpr[index],
        mlpr: response.data.mlpr[index],
      }));
      setDailyTrend(chartData);
    } catch (error) {
      console.error('Failed to fetch daily trend:', error);
    }
  };

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const params: any = {
        report_type: exportConfig.reportType,
      };

      if (exportConfig.dateRange) {
        params.date_from = exportConfig.dateRange[0].format('YYYY-MM-DD');
        params.date_to = exportConfig.dateRange[1].format('YYYY-MM-DD');
      }

      let response;
      if (exportConfig.format === 'excel') {
        response = await api.get('/export/excel', {
          params,
          responseType: 'blob',
        });
        downloadFile(response.data, 'alpr_report.xlsx');
      } else {
        response = await api.get('/export/pdf', {
          params,
          responseType: 'blob',
        });
        downloadFile(response.data, 'alpr_report.pdf');
      }

      message.success('Report exported successfully');
      setExportModalVisible(false);
    } catch (error) {
      message.error('Failed to export report');
      console.error(error);
    } finally {
      setExportLoading(false);
    }
  };

  const downloadFile = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const cameraColumns: ColumnsType<CameraStatus> = [
    {
      title: 'Camera',
      dataIndex: 'camera_name',
      key: 'camera_name',
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const color = status === 'online' ? 'green' : 'red';
        const icon = status === 'online' ? <CheckCircleOutlined /> : <CloseCircleOutlined />;
        return <Tag color={color} icon={icon}>{status.toUpperCase()}</Tag>;
      },
    },
    {
      title: 'Frames Processed',
      dataIndex: 'frame_count',
      key: 'frame_count',
      render: (count?: number) => count?.toLocaleString() || '-',
    },
    {
      title: 'Detections',
      dataIndex: 'triggered_tracks',
      key: 'triggered_tracks',
      render: (tracks?: number) => tracks || 0,
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* Header with Export Button */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
        <h1 style={{ margin: 0 }}>Dashboard</h1>
        <Button
          type="primary"
          icon={<DownloadOutlined />}
          onClick={() => setExportModalVisible(true)}
        >
          Export Report
        </Button>
      </div>

      {/* KPI Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Total Records"
              value={stats.total_records}
              prefix={<CameraOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Today's Detections"
              value={stats.today_records}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Accuracy Rate"
              value={stats.accuracy_rate}
              suffix="%"
              precision={2}
              valueStyle={{
                color: stats.accuracy_rate >= 95 ? '#3f8600' : '#cf1322',
              }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} md={6}>
          <Card>
            <Statistic
              title="Avg Confidence"
              value={stats.avg_confidence}
              suffix="%"
              precision={1}
            />
          </Card>
        </Col>
      </Row>

      {/* Status Breakdown */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col xs={24} md={8}>
          <Card title="ALPR (Automatic)">
            <Statistic
              value={stats.alpr_count}
              valueStyle={{ color: '#52c41a' }}
              suffix={
                <Progress
                  type="circle"
                  percent={
                    stats.total_records > 0
                      ? (stats.alpr_count / stats.total_records) * 100
                      : 0
                  }
                  width={60}
                  format={() => ''}
                />
              }
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="MLPR (Corrected)">
            <Statistic
              value={stats.mlpr_count}
              valueStyle={{ color: '#faad14' }}
              suffix={
                <Progress
                  type="circle"
                  percent={
                    stats.total_records > 0
                      ? (stats.mlpr_count / stats.total_records) * 100
                      : 0
                  }
                  width={60}
                  format={() => ''}
                  strokeColor="#faad14"
                />
              }
            />
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card title="Pending Verification">
            <Statistic
              value={stats.pending_count}
              valueStyle={{ color: '#1890ff' }}
              suffix={
                <Progress
                  type="circle"
                  percent={
                    stats.total_records > 0
                      ? (stats.pending_count / stats.total_records) * 100
                      : 0
                  }
                  width={60}
                  format={() => ''}
                  strokeColor="#1890ff"
                />
              }
            />
          </Card>
        </Col>
      </Row>

      {/* Multi-Camera Status */}
      <Card title="Active Cameras" style={{ marginBottom: 24 }}>
        <Table
          columns={cameraColumns}
          dataSource={cameras}
          rowKey="camera_id"
          pagination={false}
          locale={{ emptyText: 'No active cameras' }}
        />
      </Card>

      {/* Export Modal */}
      <Modal
        title="Export Report"
        open={exportModalVisible}
        onCancel={() => setExportModalVisible(false)}
        onOk={handleExport}
        confirmLoading={exportLoading}
        width={600}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          <div>
            <div style={{ marginBottom: 8 }}>Format:</div>
            <Select
              style={{ width: '100%' }}
              value={exportConfig.format}
              onChange={(value) =>
                setExportConfig({ ...exportConfig, format: value })
              }
            >
              <Option value="excel">
                <FileExcelOutlined /> Excel (.xlsx)
              </Option>
              <Option value="pdf">
                <FilePdfOutlined /> PDF
              </Option>
            </Select>
          </div>

          {exportConfig.format === 'excel' && (
            <div>
              <div style={{ marginBottom: 8 }}>Report Type:</div>
              <Select
                style={{ width: '100%' }}
                value={exportConfig.reportType}
                onChange={(value) =>
                  setExportConfig({ ...exportConfig, reportType: value })
                }
              >
                <Option value="detailed">Detailed Records</Option>
                <Option value="summary">Summary Statistics</Option>
                <Option value="analytics">Analytics Report</Option>
              </Select>
            </div>
          )}

          <div>
            <div style={{ marginBottom: 8 }}>Date Range (Optional):</div>
            <RangePicker
              style={{ width: '100%' }}
              value={exportConfig.dateRange}
              onChange={(dates) =>
                setExportConfig({
                  ...exportConfig,
                  dateRange: dates as [dayjs.Dayjs, dayjs.Dayjs] | null,
                })
              }
            />
          </div>
        </Space>
      </Modal>
    </div>
  );
};

export default DashboardPage;
