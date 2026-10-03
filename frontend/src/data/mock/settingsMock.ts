import { SettingsData } from '../../types/dashboard';

export const mockSettingsData: SettingsData = {
  title: 'Settings',
  subtitle: 'Tune alerts, camera behavior, and your profile.',
  thresholdsTitle: 'Alert Thresholds',
  thresholdsSubtitle: 'Seconds before an alert is triggered',
  thresholds: [
    { id: 'thresh-1', label: 'Yawning', seconds: 2, maxSeconds: 10 },
    { id: 'thresh-2', label: 'Phone use', seconds: 6, maxSeconds: 10 },
    { id: 'thresh-3', label: 'Bad posture', seconds: 8, maxSeconds: 10 },
    { id: 'thresh-4', label: 'Sleeping posture', seconds: 4, maxSeconds: 10 },
    { id: 'thresh-5', label: 'Away from seat', seconds: 10, maxSeconds: 10 },
  ],
  notificationsTitle: 'Alerts & Notifications',
  notifications: [
    { id: 'notif-1', label: 'Beep / sound alerts', enabled: false },
    { id: 'notif-2', label: 'On-screen banner alerts', enabled: false },
    { id: 'notif-3', label: 'Session end summary', enabled: false },
  ],
  webcamTitle: 'Webcam',
  webcam: {
    deviceLabel: 'Camera device',
    selectedDevice: 'Integrated Camera - 720p',
    previewQualityLabel: 'Preview quality',
    qualityValue: 'High · 30 FPS',
  },
  profileTitle: 'Profile',
  profile: {
    initial: 'S',
    name: 'Saurabh Kumar',
    accountType: 'Student account · Focus Monitor',
  },
};
