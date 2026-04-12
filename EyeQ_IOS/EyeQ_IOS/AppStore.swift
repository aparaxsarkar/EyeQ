import Foundation
import Combine
import UIKit
import UserNotifications

@MainActor
final class AppStore: ObservableObject {
    @Published var overview: OverviewResponse?
    @Published var incidents: [Incident] = []
    @Published var selectedIncident: Incident?
    @Published var serverURL: String
    @Published var errorMessage: String?
    @Published var notificationStatus: UNAuthorizationStatus = .notDetermined
    @Published var deviceTokenLabel = "Not registered"
    @Published var isRefreshing = false
    @Published var isSendingTestNotification = false
    @Published var notificationDebugMessage: String?

    private let api = APIClient()
    private var pollingTask: Task<Void, Never>?
    private static let defaultServerURL = "https://422a-65-113-61-98.ngrok-free.app"
    private var persistedDeviceToken: String? {
        get { UserDefaults.standard.string(forKey: "eyeq.deviceToken") }
        set { UserDefaults.standard.set(newValue, forKey: "eyeq.deviceToken") }
    }
    private var lastSurfacedIncidentID: Int {
        get { UserDefaults.standard.integer(forKey: "eyeq.lastSurfacedIncidentID") }
        set { UserDefaults.standard.set(newValue, forKey: "eyeq.lastSurfacedIncidentID") }
    }

    init() {
        self.serverURL = UserDefaults.standard.string(forKey: "eyeq.serverURL") ?? Self.defaultServerURL
    }

    func start() {
        guard pollingTask == nil else { return }

        pollingTask = Task { [weak self] in
            guard let self else { return }
            await self.refresh()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                await self.refresh(silent: true)
            }
        }

        Task {
            await refreshNotificationPermission()
            await autoRegisterForRemoteNotificationsIfNeeded()
            await retryDeviceRegistrationIfPossible()
        }
    }

    func stop() {
        pollingTask?.cancel()
        pollingTask = nil
    }

    func refresh(silent: Bool = false) async {
        if !silent {
            isRefreshing = true
        }
        defer { isRefreshing = false }

        do {
            async let overviewRequest = api.fetchOverview(baseURL: serverURL)
            async let incidentsRequest = api.fetchIncidents(baseURL: serverURL)
            let nextOverview = try await overviewRequest
            overview = nextOverview
            let nextIncidents = try await incidentsRequest
            incidents = nextIncidents
            errorMessage = nil
            await retryDeviceRegistrationIfPossible(force: nextOverview.notificationChannels.registeredDevices == 0)
            await maybeSurfaceIncidentLocally(nextIncidents, channels: nextOverview.notificationChannels)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func selectIncident(_ incident: Incident) {
        selectedIncident = incident
    }

    func openIncident(id: Int) async {
        do {
            selectedIncident = try await api.fetchIncident(baseURL: serverURL, id: id)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func saveServerURL(_ value: String) {
        serverURL = value
        UserDefaults.standard.set(value, forKey: "eyeq.serverURL")
        Task {
            await retryDeviceRegistrationIfPossible(force: true)
            await refresh()
        }
    }

    func requestNotificationPermission() async {
        do {
            let granted = try await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge])
            await refreshNotificationPermission()
            if granted {
                UIApplication.shared.registerForRemoteNotifications()
                deviceTokenLabel = "Waiting for APNs token"
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func refreshNotificationPermission() async {
        let settings = await UNUserNotificationCenter.current().notificationSettings()
        notificationStatus = settings.authorizationStatus
        if settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional || settings.authorizationStatus == .ephemeral {
            if deviceTokenLabel == "Not registered" {
                deviceTokenLabel = "Waiting for APNs token"
            }
        }
    }

    func autoRegisterForRemoteNotificationsIfNeeded() async {
        if notificationStatus == .authorized || notificationStatus == .provisional || notificationStatus == .ephemeral {
            UIApplication.shared.registerForRemoteNotifications()
        }
    }

    func registerDeviceToken(_ token: String) async {
        persistedDeviceToken = token
        deviceTokenLabel = "Registering device"
        do {
            let deviceName = UIDevice.current.name
            let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
            try await api.registerDevice(
                baseURL: serverURL,
                token: token,
                deviceName: deviceName,
                appVersion: appVersion
            )
            deviceTokenLabel = "Registered for push"
            errorMessage = nil
        } catch {
            deviceTokenLabel = "Push registration failed"
            errorMessage = error.localizedDescription
        }
    }

    func sendTestNotification() async {
        isSendingTestNotification = true
        defer { isSendingTestNotification = false }

        do {
            let response = try await api.sendTestNotification(baseURL: serverURL)
            notificationDebugMessage = response.pushSent
                ? "Push sent"
                : (response.pushConfigured ? "Push not delivered" : "Push not configured")
            errorMessage = nil
        } catch {
            notificationDebugMessage = nil
            errorMessage = error.localizedDescription
        }
    }

    private func maybeSurfaceIncidentLocally(_ incidents: [Incident], channels: NotificationChannels) async {
        guard let incident = incidents.first(where: { $0.status.lowercased() == "flagged" }) else { return }
        guard incident.status.lowercased() == "flagged" else { return }
        guard incident.id != lastSurfacedIncidentID else { return }

        lastSurfacedIncidentID = incident.id
        if !channels.pushConfigured {
            await presentLocalIncidentNotification(incident)
        }
    }

    private func retryDeviceRegistrationIfPossible(force: Bool = false) async {
        guard notificationStatus == .authorized || notificationStatus == .provisional || notificationStatus == .ephemeral else {
            return
        }
        guard let token = persistedDeviceToken, !token.isEmpty else { return }
        if !force && deviceTokenLabel == "Registered for push" {
            return
        }
        await registerDeviceToken(token)
    }

    private func presentLocalIncidentNotification(_ incident: Incident) async {
        guard notificationStatus == .authorized || notificationStatus == .provisional || notificationStatus == .ephemeral else {
            return
        }

        let content = UNMutableNotificationContent()
        content.title = "\(incident.monitorName): \(incident.severity.uppercased()) alert"
        content.body = incident.reasonShort
        content.sound = .default
        content.userInfo = ["incident_id": incident.id]

        let request = UNNotificationRequest(
            identifier: "eyeq-incident-\(incident.id)",
            content: content,
            trigger: UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        )
        try? await UNUserNotificationCenter.current().add(request)
    }
}
