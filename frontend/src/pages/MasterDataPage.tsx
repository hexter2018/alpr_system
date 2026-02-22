/**
 * Master Data Page - Province and Registered Vehicle Management
 * View and search master data for validation
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Input,
  Tag,
  Space,
  Tabs,
  Select,
  Row,
  Col,
  Statistic,
  Descriptions,
  Modal,
  message,
} from 'antd';
import {
  SearchOutlined,
  EnvironmentOutlined,
  CarOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { AxiosError } from 'axios';
import { api } from '../services/api';

const { TabPane } = Tabs;
const { Option } = Select;
const { Search } = Input;

interface Province {
  id: number;
  code: string;
  name_th: string;
  name_en: string;
  region: string;
  is_active: boolean;
}

interface RegisteredVehicle {
  id: number;
  plate_number: string;
  province_id: number;
  plate_type: string;
  vehicle_model: string | null;
  is_active: boolean;
}

const MasterDataPage: React.FC = () => {
  const [provinces, setProvinces] = useState<Province[]>([]);
  const [vehicles, setVehicles] = useState<RegisteredVehicle[]>([]);
  const [filteredProvinces, setFilteredProvinces] = useState<Province[]>([]);
  const [filteredVehicles, setFilteredVehicles] = useState<RegisteredVehicle[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);
  const [searchText, setSearchText] = useState('');
  const [vehicleDetailVisible, setVehicleDetailVisible] = useState(false);
  const [selectedVehicle, setSelectedVehicle] = useState<RegisteredVehicle | null>(null);

  useEffect(() => {
    fetchProvinces();
    fetchVehicles();
  }, []);

  useEffect(() => {
    filterProvinces();
  }, [provinces, selectedRegion, searchText]);

  const fetchProvinces = async () => {
    setLoading(true);
    try {
      const response = await api.masterData.getProvinces();
      setProvinces(response.data);
      setFilteredProvinces(response.data);
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.code !== 'ERR_NETWORK_COOLDOWN') {
        message.error('Failed to fetch provinces');
        console.error(error);
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchVehicles = async () => {
    setLoading(true);
    try {
      const response = await api.masterData.getVehicles({ limit: 100 });
      setVehicles(response.data);
      setFilteredVehicles(response.data);
    } catch (error) {
      const axiosError = error as AxiosError;
      if (axiosError.code !== 'ERR_NETWORK_COOLDOWN') {
        message.error('Failed to fetch vehicles');
        console.error(error);
      }
    } finally {
      setLoading(false);
    }
  };

  const filterProvinces = () => {
    let filtered = provinces;

    // Filter by region
    if (selectedRegion) {
      filtered = filtered.filter((p) => p.region === selectedRegion);
    }

    // Filter by search text
    if (searchText) {
      filtered = filtered.filter(
        (p) =>
          p.name_th.includes(searchText) ||
          p.name_en.toLowerCase().includes(searchText.toLowerCase()) ||
          p.code.includes(searchText)
      );
    }

    setFilteredProvinces(filtered);
  };

  const handleVehicleSearch = async (plateNumber: string) => {
    if (!plateNumber) {
      setFilteredVehicles(vehicles);
      return;
    }

    setLoading(true);
    try {
      const response = await api.masterData.searchVehicle(plateNumber);
      setFilteredVehicles([response.data]);
      message.success('Vehicle found');
    } catch (error: any) {
      if (error.response?.status === 404) {
        message.warning('Vehicle not found in database');
        setFilteredVehicles([]);
      } else {
        message.error('Search failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleViewVehicleDetail = (vehicle: RegisteredVehicle) => {
    setSelectedVehicle(vehicle);
    setVehicleDetailVisible(true);
  };

  // Get region statistics
  const getRegionStats = () => {
    const stats: { [key: string]: number } = {};
    provinces.forEach((p) => {
      stats[p.region] = (stats[p.region] || 0) + 1;
    });
    return stats;
  };

  const regionStats = getRegionStats();
  const regions = Object.keys(regionStats);

  // Province columns
  const provinceColumns: ColumnsType<Province> = [
    {
      title: 'Code',
      dataIndex: 'code',
      key: 'code',
      width: 80,
      render: (code: string) => (
        <Tag color="blue" style={{ fontSize: 14, fontFamily: 'monospace' }}>
          {code}
        </Tag>
      ),
    },
    {
      title: 'Province (Thai)',
      dataIndex: 'name_th',
      key: 'name_th',
      width: 200,
      render: (name: string) => <strong>{name}</strong>,
    },
    {
      title: 'Province (English)',
      dataIndex: 'name_en',
      key: 'name_en',
      width: 200,
    },
    {
      title: 'Region',
      dataIndex: 'region',
      key: 'region',
      width: 120,
      render: (region: string) => {
        const colors: { [key: string]: string } = {
          Central: 'gold',
          North: 'green',
          Northeast: 'orange',
          South: 'cyan',
        };
        return <Tag color={colors[region] || 'default'}>{region}</Tag>;
      },
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'} icon={active ? <CheckCircleOutlined /> : null}>
          {active ? 'Active' : 'Inactive'}
        </Tag>
      ),
    },
  ];

  // Vehicle columns
  const vehicleColumns: ColumnsType<RegisteredVehicle> = [
    {
      title: 'License Plate',
      dataIndex: 'plate_number',
      key: 'plate_number',
      width: 150,
      render: (plate: string) => (
        <Tag color="blue" style={{ fontSize: 16, fontFamily: 'monospace' }}>
          {plate}
        </Tag>
      ),
    },
    {
      title: 'Plate Type',
      dataIndex: 'plate_type',
      key: 'plate_type',
      width: 120,
      render: (type: string) => {
        const colors: { [key: string]: string } = {
          PRIVATE: 'blue',
          COMMERCIAL: 'orange',
          TAXI: 'gold',
          MOTORCYCLE: 'purple',
          GOVERNMENT: 'red',
        };
        return <Tag color={colors[type] || 'default'}>{type}</Tag>;
      },
    },
    {
      title: 'Vehicle Model',
      dataIndex: 'vehicle_model',
      key: 'vehicle_model',
      width: 200,
      render: (model: string | null) => model || '-',
    },
    {
      title: 'Status',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Tag color={active ? 'green' : 'red'}>
          {active ? 'Active' : 'Inactive'}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      width: 120,
      render: (_, record) => (
        <a onClick={() => handleViewVehicleDetail(record)}>View Details</a>
      ),
    },
  ];

  return (
    <div style={{ padding: '24px' }}>
      <h1>Master Data Management</h1>

      <Tabs defaultActiveKey="provinces">
        {/* Provinces Tab */}
        <TabPane
          tab={
            <span>
              <EnvironmentOutlined />
              Thai Provinces
            </span>
          }
          key="provinces"
        >
          {/* Statistics */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic
                  title="Total Provinces"
                  value={provinces.length}
                  prefix={<EnvironmentOutlined />}
                />
              </Card>
            </Col>
            {regions.map((region) => (
              <Col span={6} key={region}>
                <Card>
                  <Statistic title={region} value={regionStats[region]} />
                </Card>
              </Col>
            ))}
          </Row>

          {/* Filters */}
          <Card style={{ marginBottom: 16 }}>
            <Space wrap>
              <Select
                placeholder="Filter by region"
                style={{ width: 200 }}
                allowClear
                value={selectedRegion}
                onChange={setSelectedRegion}
              >
                {regions.map((region) => (
                  <Option key={region} value={region}>
                    {region}
                  </Option>
                ))}
              </Select>

              <Input
                placeholder="Search province..."
                prefix={<SearchOutlined />}
                style={{ width: 300 }}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
              />
            </Space>
          </Card>

          {/* Provinces Table */}
          <Card>
            <Table
              columns={provinceColumns}
              dataSource={filteredProvinces}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `Total ${total} provinces`,
              }}
            />
          </Card>
        </TabPane>

        {/* Registered Vehicles Tab */}
        <TabPane
          tab={
            <span>
              <CarOutlined />
              Registered Vehicles
            </span>
          }
          key="vehicles"
        >
          {/* Statistics */}
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Total Registered Vehicles"
                  value={vehicles.length}
                  prefix={<CarOutlined />}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Active Vehicles"
                  value={vehicles.filter((v) => v.is_active).length}
                  valueStyle={{ color: '#3f8600' }}
                />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic
                  title="Inactive Vehicles"
                  value={vehicles.filter((v) => !v.is_active).length}
                  valueStyle={{ color: '#cf1322' }}
                />
              </Card>
            </Col>
          </Row>

          {/* Search */}
          <Card style={{ marginBottom: 16 }}>
            <Search
              placeholder="Search by plate number (e.g., กก1234)"
              enterButton="Search"
              size="large"
              onSearch={handleVehicleSearch}
              style={{ maxWidth: 500 }}
            />
          </Card>

          {/* Vehicles Table */}
          <Card>
            <Table
              columns={vehicleColumns}
              dataSource={filteredVehicles}
              rowKey="id"
              loading={loading}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `Total ${total} vehicles`,
              }}
            />
          </Card>
        </TabPane>
      </Tabs>

      {/* Vehicle Detail Modal */}
      <Modal
        title="Vehicle Details"
        open={vehicleDetailVisible}
        onCancel={() => setVehicleDetailVisible(false)}
        footer={null}
        width={600}
      >
        {selectedVehicle && (
          <Descriptions bordered column={1}>
            <Descriptions.Item label="License Plate">
              <Tag color="blue" style={{ fontSize: 18, fontFamily: 'monospace' }}>
                {selectedVehicle.plate_number}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Plate Type">
              <Tag>{selectedVehicle.plate_type}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Vehicle Model">
              {selectedVehicle.vehicle_model || 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label="Province ID">
              {selectedVehicle.province_id}
            </Descriptions.Item>
            <Descriptions.Item label="Status">
              <Tag color={selectedVehicle.is_active ? 'green' : 'red'}>
                {selectedVehicle.is_active ? 'Active' : 'Inactive'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Record ID">
              {selectedVehicle.id}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default MasterDataPage;
