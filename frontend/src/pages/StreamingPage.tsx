/**
 * Streaming Page - RTSP Camera Management
 * Add, configure, start/stop camera streams with trigger lines
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Tag,
  Space,
  message,
  Switch,
  Drawer,
  Row,
  Col,
  Statistic,
  Select,
  Divider,
} from 'antd';
import {
  PlusOutlined,
  PlayCircleOutlined,
  StopOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CameraOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { api } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

interface Camera {
  id: number;
  name: string;
  rtsp_url: string;
  location: string | null;
  trigger_config: any;
  fps_processing: number;
  skip_frames: number;
  is_active: boolean;
  status: string;
  last_heartbeat: string | null;
}

interface StreamStatus {
  camera_id: number;
  camera_name: string;
  status: string;
  frame_count?: number;
  triggered_tracks?: number;
}

const StreamingPage: React.FC = () => {
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [activeStreams, setActiveStreams] = useState<StreamStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCamera, setEditingCamera] = useState<Camera | null>(null);
  const [configDrawerVisible, setConfigDrawerVisible] = useState(false);
  const [selectedCamera, setSelectedCamera] = useState<Camera | null>(null);
  
  const [form] = Form.useForm();

  useEffect(() => {
    fetchCameras();
    fetchActiveStreams();

    // Refresh every 10 seconds
    const interval = setInterval(() => {
      fetchCameras();
      fetchActiveStreams();
    }, 10000);

    return () => clearInterval(interval);
  }, []);

  const fetchCameras = async () => {
    try {
      const response = await api.streaming.listCameras();
      setCameras(response.data);
    } catch (error) {
      console.error('Failed to fetch cameras:', error);
    }
  };

  const fetchActiveStreams = async () => {
    try {
      const response = await api.streaming.getActiveStreams();
      setActiveStreams(response.data);
    } catch (error) {
      console.error('Failed to fetch active streams:', error);
    }
  };

  const handleAdd = () => {
    setEditingCamera(null);
    form.resetFields();
    form.setFieldsValue({
      fps_processing: 5,
      skip_frames: 3,
      trigger_config: JSON.stringify({
        type: 'line',
        coords: [[0, 360], [1280, 360]],
      }, null, 2),
    });
    setModalVisible(true);
  };

  const handleEdit = (camera: Camera) => {
    setEditingCamera(camera);
    form.setFieldsValue({
      ...camera,
      trigger_config: JSON.stringify(camera.trigger_config, null, 2),
    });
    setModalVisible(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      // Parse trigger config JSON
      let triggerConfig;
      try {
        triggerConfig = JSON.parse(values.trigger_config);
      } catch (e) {
        message.error('Invalid trigger configuration JSON');
        return;
      }

      const cameraData = {
        name: values.name,
        rtsp_url: values.rtsp_url,
        location: values.location,
        trigger_config: triggerConfig,
        fps_processing: values.fps_processing,
        skip_frames: values.skip_frames,
      };

      if (editingCamera) {
        await api.streaming.updateCamera(editingCamera.id, cameraData);
        message.success('Camera updated successfully');
      } else {
        await api.streaming.createCamera(cameraData);
        message.success('Camera created successfully');
      }

      setModalVisible(false);
      fetchCameras();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to save camera');
    }
  };

  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: 'Delete Camera',
      content: 'Are you sure you want to delete this camera?',
      onOk: async () => {
        try {
          await api.streaming.deleteCamera(id);
          message.success('Camera deleted successfully');
          fetchCameras();
        } catch (error: any) {
          message.error(error.response?.data?.detail || 'Failed to delete camera');
        }
      },
    });
  };

  const handleStartStream = async (id: number) => {
    setLoading(true);
    try {
      await api.streaming.startStream(id);
      message.success('Stream started successfully');
      fetchCameras();
      fetchActiveStreams();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to start stream');
    } finally {
      setLoading(false);
    }
  };

  const handleStopStream = async (id: number) => {
    setLoading(true);
    try {
      await api.streaming.stopStream(id);
      message.success('Stream stopped successfully');
      fetchCameras();
      fetchActiveStreams();
    } catch (error: any) {
      message.error(error.response?.data?.detail || 'Failed to stop stream');
    } finally {
      setLoading(false);
    }
  };

  const handleViewConfig = (camera: Camera) => {
    setSelectedCamera(camera);
    setConfigDrawerVisible(true);
  };

  const isStreaming = (cameraId: number): boolean => {
    return activeStreams.some((s) => s.camera_id === cameraId && s.status === 'online');
  };

  const getStreamStatus = (cameraId: number): StreamStatus | undefined => {
    return activeStreams.find((s) => s.camera_id === cameraId);
  };

  const columns: ColumnsType<Camera> = [
    {
      title: 'Camera Name',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      render: (name: string, record) => (
        <Space>
          <CameraOutlined />
          <strong>{name}</strong>
        </Space>
      ),
    },
    {
      title: 'Location',
      dataIndex: 'location',
      key: 'location',
      width: 150,
    },
    {
      title: 'RTSP URL',
      dataIndex: 'rtsp_url',
      key: 'rtsp_url',
      width: 300,
      ellipsis: true,
    },
    {
      title: 'Status',
      key: 'status',
      width: 150,
      render: (_, record) => {
        const streaming = isStreaming(record.id);
        const streamStatus = getStreamStatus(record.id);
        
        if (streaming && streamStatus) {
          return (
            <Space direction="vertical" size={0}>
              <Tag color="green" icon={<CheckCircleOutlined />}>
                STREAMING
              </Tag>
              <span style={{ fontSize: 12, color: '#666' }}>
                {streamStatus.frame_count?.toLocaleString() || 0} frames
              </span>
            </Space>
          );
        }
        
        return (
          <Tag color={record.is_active ? 'default' : 'red'} icon={<CloseCircleOutlined />}>
            {record.is_active ? 'STOPPED' : 'INACTIVE'}
          </Tag>
        );
      },
    },
    {
      title: 'Detections',
      key: 'detections',
      width: 100,
      render: (_, record) => {
        const streamStatus = getStreamStatus(record.id);
        return streamStatus?.triggered_tracks || 0;
      },
    },
    {
      title: 'FPS / Skip',
      key: 'fps_config',
      width: 120,
      render: (_, record) => (
        <div style={{ fontSize: 12 }}>
          FPS: {record.fps_processing}
          <br />
          Skip: {record.skip_frames}
        </div>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 300,
      fixed: 'right',
      render: (_, record) => {
        const streaming = isStreaming(record.id);
        
        return (
          <Space>
            {streaming ? (
              <Button
                danger
                size="small"
                icon={<StopOutlined />}
                onClick={() => handleStopStream(record.id)}
                loading={loading}
              >
                Stop
              </Button>
            ) : (
              <Button
                type="primary"
                size="small"
                icon={<PlayCircleOutlined />}
                onClick={() => handleStartStream(record.id)}
                loading={loading}
                disabled={!record.is_active}
              >
                Start
              </Button>
            )}
            
            <Button
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            >
              Edit
            </Button>
            
            <Button
              size="small"
              onClick={() => handleViewConfig(record)}
            >
              Config
            </Button>
            
            <Button
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => handleDelete(record.id)}
            >
              Delete
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* Header */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between' }}>
        <h1>RTSP Camera Streaming</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          Add Camera
        </Button>
      </div>

      {/* Statistics */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Cameras"
              value={cameras.length}
              prefix={<CameraOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Active Streams"
              value={activeStreams.length}
              valueStyle={{ color: '#3f8600' }}
              prefix={<SyncOutlined spin />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Frames"
              value={activeStreams.reduce((sum, s) => sum + (s.frame_count || 0), 0)}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Total Detections"
              value={activeStreams.reduce((sum, s) => sum + (s.triggered_tracks || 0), 0)}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Cameras Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={cameras}
          rowKey="id"
          loading={loading}
          scroll={{ x: 1500 }}
        />
      </Card>

      {/* Add/Edit Modal */}
      <Modal
        title={editingCamera ? 'Edit Camera' : 'Add Camera'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSubmit}
        width={700}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="Camera Name"
            name="name"
            rules={[{ required: true, message: 'Please enter camera name' }]}
          >
            <Input placeholder="e.g., Main Gate Camera" />
          </Form.Item>

          <Form.Item
            label="RTSP URL"
            name="rtsp_url"
            rules={[
              { required: true, message: 'Please enter RTSP URL' },
              { pattern: /^rtsp:\/\/.*/, message: 'URL must start with rtsp://' },
            ]}
          >
            <Input placeholder="rtsp://username:password@192.168.1.100:554/stream" />
          </Form.Item>

          <Form.Item label="Location" name="location">
            <Input placeholder="e.g., Building A - Main Entrance" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                label="FPS Processing"
                name="fps_processing"
                tooltip="Process every Nth frame (higher = more detections but slower)"
              >
                <InputNumber min={1} max={30} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                label="Skip Frames"
                name="skip_frames"
                tooltip="Skip N frames between processing (higher = faster but less accurate)"
              >
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            label="Trigger Configuration (JSON)"
            name="trigger_config"
            rules={[
              { required: true, message: 'Please enter trigger configuration' },
            ]}
          >
            <TextArea
              rows={6}
              placeholder={`{
  "type": "line",
  "coords": [[0, 360], [1280, 360]]
}`}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>

          <div style={{ padding: 12, backgroundColor: '#f0f2f5', borderRadius: 4 }}>
            <strong>Trigger Configuration Examples:</strong>
            <pre style={{ fontSize: 11, marginTop: 8 }}>
              {`// Horizontal line (default)
{
  "type": "line",
  "coords": [[0, 360], [1280, 360]]
}

// Vertical line
{
  "type": "line",
  "coords": [[640, 0], [640, 720]]
}

// Region of Interest (ROI)
{
  "type": "roi",
  "polygon": [[100,100], [1180,100], [1180,620], [100,620]]
}`}
            </pre>
          </div>
        </Form>
      </Modal>

      {/* Configuration Drawer */}
      <Drawer
        title="Camera Configuration"
        placement="right"
        onClose={() => setConfigDrawerVisible(false)}
        open={configDrawerVisible}
        width={500}
      >
        {selectedCamera && (
          <div>
            <Divider orientation="left">Basic Info</Divider>
            <div style={{ marginBottom: 16 }}>
              <strong>Name:</strong> {selectedCamera.name}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>Location:</strong> {selectedCamera.location || 'N/A'}
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>RTSP URL:</strong>
              <div style={{ wordBreak: 'break-all', fontSize: 12, color: '#666' }}>
                {selectedCamera.rtsp_url}
              </div>
            </div>

            <Divider orientation="left">Processing Settings</Divider>
            <Row gutter={16}>
              <Col span={12}>
                <Card size="small">
                  <Statistic
                    title="FPS Processing"
                    value={selectedCamera.fps_processing}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card size="small">
                  <Statistic title="Skip Frames" value={selectedCamera.skip_frames} />
                </Card>
              </Col>
            </Row>

            <Divider orientation="left">Trigger Configuration</Divider>
            <pre
              style={{
                padding: 12,
                backgroundColor: '#f5f5f5',
                borderRadius: 4,
                fontSize: 12,
                overflow: 'auto',
              }}
            >
              {JSON.stringify(selectedCamera.trigger_config, null, 2)}
            </pre>

            <Divider orientation="left">Status</Divider>
            <div style={{ marginBottom: 16 }}>
              <strong>Active:</strong>{' '}
              <Tag color={selectedCamera.is_active ? 'green' : 'red'}>
                {selectedCamera.is_active ? 'Yes' : 'No'}
              </Tag>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>Status:</strong>{' '}
              <Tag color={selectedCamera.status === 'online' ? 'green' : 'default'}>
                {selectedCamera.status.toUpperCase()}
              </Tag>
            </div>
            {selectedCamera.last_heartbeat && (
              <div>
                <strong>Last Heartbeat:</strong>
                <div style={{ fontSize: 12, color: '#666' }}>
                  {new Date(selectedCamera.last_heartbeat).toLocaleString()}
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default StreamingPage;