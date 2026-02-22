/**
 * Upload Page - Single and Batch Image Upload
 * Drag-and-drop interface with instant processing
 */

import React, { useState } from 'react';
import {
  Upload,
  Card,
  Button,
  Table,
  Image,
  Tag,
  Progress,
  Space,
  message,
  Tabs,
  Alert,
  Row,
  Col,
  Statistic,
} from 'antd';
import {
  InboxOutlined,
  UploadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { UploadProps, UploadFile } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { api } from '../services/api';

const { Dragger } = Upload;
const { TabPane } = Tabs;

interface ProcessingResult {
  record_id: number;
  plate_number: string;
  province_code: string | null;
  province_name: string | null;
  confidence: number;
  is_registered: boolean;
  status: string;
  cropped_image_url: string;
  original_image_url: string;
  processing_time_ms: number;
  file_name?: string;
  error?: string;
}

const UploadPage: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState<ProcessingResult[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [activeTab, setActiveTab] = useState('single');
  
  // Statistics
  const [stats, setStats] = useState({
    total: 0,
    successful: 0,
    failed: 0,
  });

  // Single file upload
  const handleSingleUpload = async (file: File) => {
    setUploading(true);
    try {
      const response = await api.upload.single(file);
      const result = { ...response.data, file_name: file.name };
      
      setResults([result]);
      setStats({ total: 1, successful: 1, failed: 0 });
      
      message.success(`License plate detected: ${result.plate_number}`);
    } catch (error: any) {
      message.error(`Upload failed: ${error.response?.data?.detail || error.message}`);
      setResults([{
        record_id: 0,
        plate_number: 'Error',
        province_code: null,
        province_name: null,
        confidence: 0,
        is_registered: false,
        status: 'FAILED',
        cropped_image_url: '',
        original_image_url: '',
        processing_time_ms: 0,
        file_name: file.name,
        error: error.response?.data?.detail || error.message,
      }]);
      setStats({ total: 1, successful: 0, failed: 1 });
    } finally {
      setUploading(false);
    }
  };

  // Batch file upload
  const handleBatchUpload = async (files: File[]) => {
    setUploading(true);
    setResults([]);
    
    try {
      const response = await api.upload.batch(files);
      const batchResults = response.data.results.map((r: any, i: number) => ({
        ...r,
        file_name: files[i]?.name || `File ${i + 1}`,
      }));
      
      setResults(batchResults);
      setStats({
        total: response.data.total_images,
        successful: response.data.successful,
        failed: response.data.failed,
      });
      
      message.success(
        `Batch upload complete: ${response.data.successful} successful, ${response.data.failed} failed`
      );
    } catch (error: any) {
      message.error(`Batch upload failed: ${error.response?.data?.detail || error.message}`);
      setStats({ total: files.length, successful: 0, failed: files.length });
    } finally {
      setUploading(false);
      setFileList([]);
    }
  };

  // Single upload props
  const singleUploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: 'image/jpeg,image/jpg,image/png',
    beforeUpload: (file) => {
      const isImage = file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/jpg';
      if (!isImage) {
        message.error('You can only upload JPG/PNG files!');
        return false;
      }
      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error('Image must be smaller than 10MB!');
        return false;
      }
      
      handleSingleUpload(file);
      return false; // Prevent auto upload
    },
    showUploadList: false,
  };

  // Batch upload props
  const batchUploadProps: UploadProps = {
    name: 'files',
    multiple: true,
    accept: 'image/jpeg,image/jpg,image/png',
    fileList,
    beforeUpload: (file) => {
      const isImage = file.type === 'image/jpeg' || file.type === 'image/png' || file.type === 'image/jpg';
      if (!isImage) {
        message.error(`${file.name} is not an image file`);
        return false;
      }
      const isLt10M = file.size / 1024 / 1024 < 10;
      if (!isLt10M) {
        message.error(`${file.name} must be smaller than 10MB!`);
        return false;
      }
      return false; // Prevent auto upload
    },
    onChange: (info) => {
      setFileList(info.fileList);
    },
    onRemove: (file) => {
      setFileList((prev) => prev.filter((f) => f.uid !== file.uid));
    },
  };

  const handleBatchSubmit = () => {
    if (fileList.length === 0) {
      message.warning('Please select at least one image');
      return;
    }
    if (fileList.length > 50) {
      message.error('Maximum 50 images per batch');
      return;
    }
    
    const files = fileList.map((f) => f.originFileObj as File);
    handleBatchUpload(files);
  };

  // Results table columns
  const columns: ColumnsType<ProcessingResult> = [
    {
      title: 'File',
      dataIndex: 'file_name',
      key: 'file_name',
      width: 150,
      ellipsis: true,
    },
    {
      title: 'Cropped Plate',
      dataIndex: 'cropped_image_url',
      key: 'cropped_image',
      width: 150,
      render: (url: string, record) => {
        if (record.error) return '-';
        return (
          <Image
            src={url}
            alt={record.plate_number}
            width={120}
            height={60}
            style={{ objectFit: 'cover' }}
          />
        );
      },
    },
    {
      title: 'License Plate',
      key: 'plate_info',
      width: 200,
      render: (_, record) => {
        if (record.error) {
          return <Tag color="red">Error: {record.error}</Tag>;
        }
        return (
          <Space direction="vertical" size={2}>
            <div style={{ fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace' }}>
              {record.plate_number}
            </div>
            {record.province_name && (
              <div style={{ fontSize: 12, color: '#666' }}>
                {record.province_name} ({record.province_code})
              </div>
            )}
          </Space>
        );
      },
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (confidence: number) => {
        const percent = confidence * 100;
        const color = percent >= 90 ? 'green' : percent >= 70 ? 'orange' : 'red';
        return (
          <Progress
            type="circle"
            percent={Math.round(percent)}
            width={50}
            strokeColor={color}
          />
        );
      },
      sorter: (a, b) => a.confidence - b.confidence,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string, record) => {
        if (record.error) {
          return <Tag color="red" icon={<CloseCircleOutlined />}>FAILED</Tag>;
        }
        const color = status === 'ALPR' ? 'green' : 'orange';
        const icon = status === 'ALPR' ? <CheckCircleOutlined /> : <SyncOutlined />;
        return <Tag color={color} icon={icon}>{status}</Tag>;
      },
    },
    {
      title: 'Registered',
      dataIndex: 'is_registered',
      key: 'is_registered',
      width: 100,
      render: (registered: boolean) => (
        <Tag color={registered ? 'green' : 'default'}>
          {registered ? 'Yes' : 'No'}
        </Tag>
      ),
    },
    {
      title: 'Processing Time',
      dataIndex: 'processing_time_ms',
      key: 'processing_time',
      width: 130,
      render: (time: number) => `${time} ms`,
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      render: (_, record) => {
        if (record.error) return null;
        return (
          <Button
            type="link"
            size="small"
            onClick={() => {
              window.location.href = `/verification?record_id=${record.record_id}`;
            }}
          >
            View Details
          </Button>
        );
      },
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <h1>Upload Images</h1>

      <Tabs activeKey={activeTab} onChange={setActiveTab}>
        {/* Single Upload Tab */}
        <TabPane tab="Single Image" key="single">
          <Card>
            <Alert
              message="Single Image Upload"
              description="Upload a single image for instant license plate detection. Supports JPG and PNG formats up to 10MB."
              type="info"
              showIcon
              style={{ marginBottom: 24 }}
            />

            <Dragger {...singleUploadProps} style={{ marginBottom: 24 }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Click or drag image to this area to upload</p>
              <p className="ant-upload-hint">
                Supports JPG, JPEG, PNG. Maximum file size: 10MB.
              </p>
            </Dragger>

            {uploading && (
              <div style={{ textAlign: 'center', padding: '20px' }}>
                <SyncOutlined spin style={{ fontSize: 24 }} />
                <div style={{ marginTop: 10 }}>Processing image...</div>
              </div>
            )}
          </Card>
        </TabPane>

        {/* Batch Upload Tab */}
        <TabPane tab="Batch Upload" key="batch">
          <Card>
            <Alert
              message="Batch Image Upload"
              description="Upload multiple images at once for batch processing. Maximum 50 images per batch."
              type="info"
              showIcon
              style={{ marginBottom: 24 }}
            />

            <Dragger {...batchUploadProps} style={{ marginBottom: 24 }}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">Click or drag images to this area to upload</p>
              <p className="ant-upload-hint">
                Supports multiple JPG, JPEG, PNG files. Maximum 50 images, 10MB each.
              </p>
            </Dragger>

            {fileList.length > 0 && (
              <>
                <div style={{ marginBottom: 16 }}>
                  <strong>Selected: {fileList.length} files</strong>
                </div>
                <Button
                  type="primary"
                  icon={<UploadOutlined />}
                  onClick={handleBatchSubmit}
                  loading={uploading}
                  size="large"
                  block
                >
                  Process {fileList.length} Images
                </Button>
              </>
            )}

            {uploading && (
              <div style={{ textAlign: 'center', padding: '20px', marginTop: 20 }}>
                <SyncOutlined spin style={{ fontSize: 24 }} />
                <div style={{ marginTop: 10 }}>Processing {fileList.length} images...</div>
                <Progress
                  percent={Math.round((stats.successful + stats.failed) / stats.total * 100)}
                  status="active"
                  style={{ marginTop: 10 }}
                />
              </div>
            )}
          </Card>
        </TabPane>
      </Tabs>

      {/* Results Section */}
      {results.length > 0 && (
        <Card title="Processing Results" style={{ marginTop: 24 }}>
          {/* Statistics */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}>
              <Card>
                <Statistic title="Total Processed" value={stats.total} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Successful"
                  value={stats.successful}
                  valueStyle={{ color: '#3f8600' }}
                  prefix={<CheckCircleOutlined />}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Failed"
                  value={stats.failed}
                  valueStyle={{ color: '#cf1322' }}
                  prefix={<CloseCircleOutlined />}
                />
              </Card>
            </Col>
          </Row>

          {/* Results Table */}
          <Table
            columns={columns}
            dataSource={results}
            rowKey={(record) => record.record_id || record.file_name || Math.random()}
            pagination={false}
            scroll={{ x: 1200 }}
          />
        </Card>
      )}
    </div>
  );
};

export default UploadPage;
