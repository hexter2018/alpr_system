/**
 * Verification Page - MLPR Correction Interface
 * Displays OCR results with cropped plate images for human verification
 * Admins can edit incorrect results, changing status from ALPR to MLPR
 */

import React, { useState, useEffect } from 'react';
import {
  Table,
  Image,
  Input,
  Button,
  Modal,
  Tag,
  Space,
  message,
  Select,
  DatePicker,
  Card,
  Statistic,
  Row,
  Col,
  Form,
  Pagination
} from 'antd';
import {
  EditOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SearchOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import type { AxiosError } from 'axios';
import { apiClient } from '../services/api';

const { RangePicker } = DatePicker;
const { Option } = Select;

interface PlateRecord {
  id: number;
  plate_number: string;
  province_code: string | null;
  province_name: string | null;
  confidence: number;
  status: 'ALPR' | 'MLPR' | 'PENDING' | 'REJECTED';
  is_registered: boolean;
  cropped_image_url: string;
  original_image_url: string;
  capture_timestamp: string;
  processing_mode: string;
  was_corrected: boolean;
  corrected_plate_number?: string;
  corrected_province_code?: string;
  correction_timestamp?: string;
}

interface FilterState {
  status?: string;
  processing_mode?: string;
  date_range?: [dayjs.Dayjs, dayjs.Dayjs];
  plate_number?: string;
  province_code?: string;
  min_confidence?: number;
  max_confidence?: number;
}

const VerificationPage: React.FC = () => {
  const [records, setRecords] = useState<PlateRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [totalRecords, setTotalRecords] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  // Stats
  const [stats, setStats] = useState({
    total_records: 0,
    alpr_count: 0,
    mlpr_count: 0,
    pending_count: 0,
    accuracy_rate: 0,
    correction_rate: 0
  });
  
  // Filters
  const [filters, setFilters] = useState<FilterState>({});
  
  // Edit modal
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<PlateRecord | null>(null);
  const [editForm] = Form.useForm();

  // Load data
  useEffect(() => {
    fetchRecords();
    fetchStats();
  }, [currentPage, pageSize, filters]);

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const params: any = {
        page: currentPage,
        page_size: pageSize,
      };

      if (filters.status) params.status = filters.status;
      if (filters.processing_mode) params.processing_mode = filters.processing_mode;
      if (filters.plate_number) params.plate_number = filters.plate_number;
      if (filters.province_code) params.province_code = filters.province_code;
      if (filters.min_confidence !== undefined) params.min_confidence = filters.min_confidence;
      if (filters.max_confidence !== undefined) params.max_confidence = filters.max_confidence;
      
      if (filters.date_range) {
        params.date_from = filters.date_range[0].toISOString();
        params.date_to = filters.date_range[1].toISOString();
      }

      const response = await apiClient.get('/verification/list', { params });
      
      setRecords(response.data.records);
      setTotalRecords(response.data.total);
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.code !== 'ERR_NETWORK_COOLDOWN') {
        message.error('Failed to load records');
        console.error(error);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await apiClient.get('/verification/stats/summary');
      setStats(response.data);
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.code !== 'ERR_NETWORK_COOLDOWN') {
        console.error('Failed to load stats:', error);
      }
    }
  };

  const handleEdit = (record: PlateRecord) => {
    setEditingRecord(record);
    editForm.setFieldsValue({
      corrected_plate_number: record.plate_number,
      corrected_province_code: record.province_code,
      correction_reason: ''
    });
    setEditModalVisible(true);
  };

  const handleSaveCorrection = async () => {
    try {
      const values = await editForm.validateFields();
      
      if (!editingRecord) return;

      // Call API to save correction
      await apiClient.post(`/verification/${editingRecord.id}/correct`, {
        corrected_plate_number: values.corrected_plate_number,
        corrected_province_code: values.corrected_province_code,
        correction_reason: values.correction_reason,
        user_id: 1  // TODO: Get from auth context
      });

      message.success('Correction saved successfully. Status changed to MLPR.');
      setEditModalVisible(false);
      setEditingRecord(null);
      fetchRecords();
      fetchStats();
    } catch (error) {
      message.error('Failed to save correction');
      console.error(error);
    }
  };

  const columns: ColumnsType<PlateRecord> = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: 'Cropped Plate',
      dataIndex: 'cropped_image_url',
      key: 'cropped_image',
      width: 150,
      render: (url: string, record) => (
        <Image
          src={url}
          alt={`Plate ${record.plate_number}`}
          width={120}
          height={60}
          style={{ objectFit: 'cover', border: '1px solid #d9d9d9', borderRadius: 4 }}
          preview={{
            mask: 'Preview'
          }}
        />
      ),
    },
    {
      title: 'License Plate',
      key: 'plate_info',
      width: 200,
      render: (_, record) => (
        <Space direction="vertical" size={2}>
          <div style={{ fontSize: 16, fontWeight: 'bold', fontFamily: 'monospace' }}>
            {record.plate_number}
          </div>
          {record.province_name && (
            <div style={{ fontSize: 12, color: '#666' }}>
              {record.province_name} ({record.province_code})
            </div>
          )}
          {record.was_corrected && (
            <Tag color="orange" style={{ marginTop: 4 }}>
              Corrected from: {record.plate_number !== record.corrected_plate_number ? record.plate_number : 'province only'}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: 'Confidence',
      dataIndex: 'confidence',
      key: 'confidence',
      width: 120,
      render: (confidence: number) => {
        const color = confidence >= 0.9 ? 'green' : confidence >= 0.7 ? 'orange' : 'red';
        return (
          <Tag color={color}>
            {(confidence * 100).toFixed(1)}%
          </Tag>
        );
      },
      sorter: (a, b) => a.confidence - b.confidence,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const config = {
          ALPR: { color: 'green', icon: <CheckCircleOutlined /> },
          MLPR: { color: 'orange', icon: <EditOutlined /> },
          PENDING: { color: 'blue', icon: <CloseCircleOutlined /> },
          REJECTED: { color: 'red', icon: <CloseCircleOutlined /> }
        };
        const { color, icon } = config[status as keyof typeof config] || {};
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
      title: 'Capture Time',
      dataIndex: 'capture_timestamp',
      key: 'capture_timestamp',
      width: 180,
      render: (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss'),
      sorter: (a, b) => dayjs(a.capture_timestamp).unix() - dayjs(b.capture_timestamp).unix(),
    },
    {
      title: 'Mode',
      dataIndex: 'processing_mode',
      key: 'processing_mode',
      width: 120,
      render: (mode: string) => {
        const color = mode.includes('STREAM') ? 'purple' : 'blue';
        return <Tag color={color}>{mode.replace('_', ' ')}</Tag>;
      },
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 100,
      fixed: 'right',
      render: (_, record) => (
        <Button
          type="primary"
          size="small"
          icon={<EditOutlined />}
          onClick={() => handleEdit(record)}
        >
          Edit
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      {/* Statistics Cards */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card>
            <Statistic title="Total Records" value={stats.total_records} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="ALPR (Auto)"
              value={stats.alpr_count}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="MLPR (Corrected)"
              value={stats.mlpr_count}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="Pending" value={stats.pending_count} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="Accuracy Rate"
              value={stats.accuracy_rate}
              suffix="%"
              precision={2}
              valueStyle={{ color: stats.accuracy_rate >= 95 ? '#3f8600' : '#cf1322' }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="Correction Rate"
              value={stats.correction_rate}
              suffix="%"
              precision={2}
            />
          </Card>
        </Col>
      </Row>

      {/* Filters */}
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            placeholder="Status"
            style={{ width: 120 }}
            allowClear
            value={filters.status}
            onChange={(value) => setFilters({ ...filters, status: value })}
          >
            <Option value="ALPR">ALPR</Option>
            <Option value="MLPR">MLPR</Option>
            <Option value="PENDING">PENDING</Option>
          </Select>

          <Select
            placeholder="Processing Mode"
            style={{ width: 150 }}
            allowClear
            value={filters.processing_mode}
            onChange={(value) => setFilters({ ...filters, processing_mode: value })}
          >
            <Option value="IMAGE_SINGLE">Single Image</Option>
            <Option value="IMAGE_BATCH">Batch</Option>
            <Option value="STREAM_RTSP">RTSP Stream</Option>
          </Select>

          <Input
            placeholder="Search plate number"
            prefix={<SearchOutlined />}
            style={{ width: 200 }}
            value={filters.plate_number}
            onChange={(e) => setFilters({ ...filters, plate_number: e.target.value })}
          />

          <RangePicker
            value={filters.date_range}
            onChange={(dates) => setFilters({ ...filters, date_range: dates as [dayjs.Dayjs, dayjs.Dayjs] })}
          />

          <Button
            icon={<ReloadOutlined />}
            onClick={() => {
              setFilters({});
              fetchRecords();
            }}
          >
            Reset
          </Button>
        </Space>
      </Card>

      {/* Table */}
      <Card>
        <Table
          columns={columns}
          dataSource={records}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1500 }}
        />
        
        <div style={{ marginTop: 16, textAlign: 'right' }}>
          <Pagination
            current={currentPage}
            pageSize={pageSize}
            total={totalRecords}
            onChange={(page, pageSize) => {
              setCurrentPage(page);
              setPageSize(pageSize);
            }}
            showSizeChanger
            showTotal={(total) => `Total ${total} records`}
          />
        </div>
      </Card>

      {/* Edit Modal */}
      <Modal
        title="Correct License Plate"
        open={editModalVisible}
        onOk={handleSaveCorrection}
        onCancel={() => {
          setEditModalVisible(false);
          setEditingRecord(null);
        }}
        width={700}
      >
        {editingRecord && (
          <div>
            {/* Display current image and OCR result */}
            <div style={{ marginBottom: 24, textAlign: 'center' }}>
              <Image
                src={editingRecord.cropped_image_url}
                alt="License Plate"
                style={{ maxWidth: '100%', maxHeight: 200, border: '2px solid #1890ff' }}
              />
              <div style={{ marginTop: 12, fontSize: 16 }}>
                <strong>Current OCR Result:</strong> {editingRecord.plate_number}
                {editingRecord.province_name && ` (${editingRecord.province_name})`}
              </div>
              <div style={{ fontSize: 14, color: '#666' }}>
                Confidence: {(editingRecord.confidence * 100).toFixed(1)}%
              </div>
            </div>

            {/* Correction Form */}
            <Form form={editForm} layout="vertical">
              <Form.Item
                label="Corrected Plate Number"
                name="corrected_plate_number"
                rules={[{ required: true, message: 'Please enter the correct plate number' }]}
              >
                <Input
                  size="large"
                  placeholder="e.g., กก1234"
                  style={{ fontSize: 18, fontFamily: 'monospace' }}
                />
              </Form.Item>

              <Form.Item
                label="Corrected Province Code"
                name="corrected_province_code"
              >
                <Input
                  size="large"
                  placeholder="e.g., กท"
                  style={{ fontSize: 18 }}
                />
              </Form.Item>

              <Form.Item
                label="Correction Reason (Optional)"
                name="correction_reason"
              >
                <Input.TextArea
                  rows={3}
                  placeholder="Why was this correction made?"
                />
              </Form.Item>
            </Form>

            <div style={{ padding: 12, backgroundColor: '#fff7e6', border: '1px solid #ffd591', borderRadius: 4 }}>
              ⚠️ <strong>Note:</strong> After saving, this record's status will change to <Tag color="orange">MLPR</Tag> 
              and will be used for continuous learning to improve the OCR model.
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default VerificationPage;
