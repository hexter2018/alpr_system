/**
 * Real-time Notification Component
 * Connects to WebSocket and displays notifications
 */

import React, { useEffect, useState, useCallback } from 'react';
import { notification, Badge, Drawer, List, Tag, Typography } from 'antd';
import {
  BellOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

interface Notification {
  type: string;
  priority: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  message: string;
  data: any;
  timestamp: string;
}

const NotificationCenter: React.FC = () => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [ws, setWs] = useState<WebSocket | null>(null);

  const wsBaseUrl = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;

  // Connect to WebSocket
  useEffect(() => {
    const userId = localStorage.getItem('user_id') || '1'; // TODO: Get from auth
    const token = localStorage.getItem('access_token');
    const encodedToken = token ? encodeURIComponent(token) : '';
    
    const websocket = new WebSocket(
      `${wsBaseUrl}/api/ws/notifications?user_id=${userId}&token=${encodedToken}`
    );

    websocket.onopen = () => {
      console.log('✅ WebSocket connected');
    };

    websocket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      handleNotification(data);
    };

    websocket.onerror = (error) => {
      console.error('❌ WebSocket error:', error);
    };

    websocket.onclose = () => {
      console.log('🔌 WebSocket disconnected');
      // Attempt reconnection after 5 seconds
      setTimeout(() => {
        console.log('🔄 Reconnecting...');
        // Trigger re-render to reconnect
      }, 5000);
    };

    setWs(websocket);

    // Cleanup on unmount
    return () => {
      websocket.close();
    };
  }, [wsBaseUrl]);

  const handleNotification = useCallback((notif: Notification) => {
    // Add to notifications list
    setNotifications((prev) => [notif, ...prev].slice(0, 50)); // Keep last 50
    setUnreadCount((prev) => prev + 1);

    // Display Ant Design notification
    const { type, priority, title, message } = notif;

    let icon;
    let duration = 4.5;

    // Set icon and duration based on priority
    switch (priority) {
      case 'critical':
        icon = <WarningOutlined style={{ color: '#ff4d4f' }} />;
        duration = 0; // Don't auto-close
        break;
      case 'high':
        icon = <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
        duration = 10;
        break;
      case 'medium':
        icon = <InfoCircleOutlined style={{ color: '#1890ff' }} />;
        duration = 6;
        break;
      default:
        icon = <CheckCircleOutlined style={{ color: '#52c41a' }} />;
        duration = 4.5;
    }

    // Show notification
    notification.open({
      message: title,
      description: message,
      icon,
      duration,
      placement: 'topRight',
      onClick: () => {
        // Handle click - navigate to relevant page
        handleNotificationClick(notif);
      },
    });

    // Play sound for high/critical priority
    if (priority === 'high' || priority === 'critical') {
      playNotificationSound();
    }
  }, []);

  const handleNotificationClick = (notif: Notification) => {
    // Navigate based on notification type
    switch (notif.type) {
      case 'new_detection':
      case 'low_confidence':
        // Navigate to verification page
        window.location.href = `/verification?record_id=${notif.data.record_id}`;
        break;
      case 'mlpr_correction':
        window.location.href = `/verification?record_id=${notif.data.record_id}`;
        break;
      case 'stream_started':
      case 'stream_stopped':
        window.location.href = `/streaming?camera_id=${notif.data.camera_id}`;
        break;
    }
  };

  const playNotificationSound = () => {
    // Play a subtle notification sound
    const audio = new Audio('/notification.mp3');
    audio.volume = 0.3;
    audio.play().catch(() => {
      // Ignore if audio can't play
    });
  };

  const markAllAsRead = () => {
    setUnreadCount(0);
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical':
        return 'red';
      case 'high':
        return 'orange';
      case 'medium':
        return 'blue';
      default:
        return 'default';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'new_detection':
        return <CheckCircleOutlined />;
      case 'low_confidence':
        return <ExclamationCircleOutlined />;
      case 'mlpr_correction':
        return <InfoCircleOutlined />;
      case 'stream_started':
      case 'stream_stopped':
        return <BellOutlined />;
      default:
        return <InfoCircleOutlined />;
    }
  };

  return (
    <>
      {/* Bell icon with badge */}
      <Badge count={unreadCount} offset={[-5, 5]}>
        <BellOutlined
          style={{ fontSize: 20, cursor: 'pointer' }}
          onClick={() => {
            setDrawerVisible(true);
            markAllAsRead();
          }}
        />
      </Badge>

      {/* Notification drawer */}
      <Drawer
        title="Notifications"
        placement="right"
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
        width={400}
      >
        <List
          dataSource={notifications}
          renderItem={(item) => (
            <List.Item
              style={{ cursor: 'pointer' }}
              onClick={() => handleNotificationClick(item)}
            >
              <List.Item.Meta
                avatar={getTypeIcon(item.type)}
                title={
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text strong>{item.title}</Text>
                    <Tag color={getPriorityColor(item.priority)}>
                      {item.priority}
                    </Tag>
                  </div>
                }
                description={
                  <>
                    <Text>{item.message}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(item.timestamp).toLocaleString()}
                    </Text>
                  </>
                }
              />
            </List.Item>
          )}
          locale={{ emptyText: 'No notifications' }}
        />

        {notifications.length > 0 && (
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <a onClick={() => setNotifications([])}>Clear All</a>
          </div>
        )}
      </Drawer>
    </>
  );
};

export default NotificationCenter;
