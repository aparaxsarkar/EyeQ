import Foundation

struct OverviewResponse: Codable {
    let monitor: MonitorOverview
    let latestIncident: Incident?
    let notificationChannels: NotificationChannels

    enum CodingKeys: String, CodingKey {
        case monitor
        case latestIncident = "latest_incident"
        case notificationChannels = "notification_channels"
    }
}

struct NotificationChannels: Codable {
    let pushConfigured: Bool
    let registeredDevices: Int

    enum CodingKeys: String, CodingKey {
        case pushConfigured = "push_configured"
        case registeredDevices = "registered_devices"
    }
}

struct MonitorOverview: Codable {
    let name: String
    let running: Bool
    let watchState: String
    let uptimeSeconds: Int
    let peopleCount: Int
    let lastHeuristicReason: String
    let lastClassifierReason: String
    let lastClassifierSeverity: String
    let lastReviewLatencyMs: Int
    let latestSnapshotURL: URL?
    let liveFrameURL: URL?
    let liveStreamURL: URL?

    enum CodingKeys: String, CodingKey {
        case name
        case running
        case watchState = "watch_state"
        case uptimeSeconds = "uptime_seconds"
        case peopleCount = "people_count"
        case lastHeuristicReason = "last_heuristic_reason"
        case lastClassifierReason = "last_classifier_reason"
        case lastClassifierSeverity = "last_classifier_severity"
        case lastReviewLatencyMs = "last_review_latency_ms"
        case latestSnapshotURL = "latest_snapshot_url"
        case liveFrameURL = "live_frame_url"
        case liveStreamURL = "live_stream_url"
    }
}

struct IncidentsResponse: Codable {
    let items: [Incident]
}

struct Incident: Codable, Identifiable, Hashable {
    let id: Int
    let status: String
    let severity: String
    let source: String
    let monitorName: String
    let startedAt: String
    let updatedAt: String
    let heuristicReason: String
    let classifierReason: String
    let reasonShort: String
    let suggestedAction: String
    let reviewLatencyMs: Int
    let snapshotURL: URL?
    let clipURL: URL?
    let clipReady: Bool
    let notifiedPush: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case status
        case severity
        case source
        case monitorName = "monitor_name"
        case startedAt = "started_at"
        case updatedAt = "updated_at"
        case heuristicReason = "heuristic_reason"
        case classifierReason = "classifier_reason"
        case reasonShort = "reason_short"
        case suggestedAction = "suggested_action"
        case reviewLatencyMs = "review_latency_ms"
        case snapshotURL = "snapshot_url"
        case clipURL = "clip_url"
        case clipReady = "clip_ready"
        case notifiedPush = "notified_push"
    }
}

struct DeviceRegistrationPayload: Codable {
    let platform: String
    let token: String
    let deviceName: String
    let appVersion: String
    let notificationsEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case platform
        case token
        case deviceName = "device_name"
        case appVersion = "app_version"
        case notificationsEnabled = "notifications_enabled"
    }
}

struct TestNotificationResponse: Codable {
    let pushSent: Bool
    let pushConfigured: Bool
    let incidentID: Int?

    enum CodingKeys: String, CodingKey {
        case pushSent = "push_sent"
        case pushConfigured = "push_configured"
        case incidentID = "incident_id"
    }
}
