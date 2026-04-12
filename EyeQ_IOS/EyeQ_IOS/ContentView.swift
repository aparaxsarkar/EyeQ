import SwiftUI
import UserNotifications

struct ContentView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        TabView {
            NavigationStack {
                HomeView()
            }
            .tabItem {
                Label("Home", systemImage: "shield.lefthalf.filled")
            }

            NavigationStack {
                LiveView()
            }
            .tabItem {
                Label("Live", systemImage: "video.fill")
            }

            NavigationStack {
                AlertsView()
            }
            .tabItem {
                Label("Alerts", systemImage: "bell.badge.fill")
            }

            NavigationStack {
                SettingsView()
            }
            .tabItem {
                Label("Settings", systemImage: "gearshape.fill")
            }
        }
        .task {
            store.start()
        }
        .sheet(item: $store.selectedIncident) { incident in
            IncidentDetailView(incident: incident)
        }
        .alert("Connection problem", isPresented: Binding(
            get: { store.errorMessage != nil },
            set: { isPresented in
                if !isPresented {
                    store.errorMessage = nil
                }
            })
        ) {
            Button("Dismiss", role: .cancel) {}
        } message: {
            Text(store.errorMessage ?? "")
        }
    }
}

private struct HomeView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let overview = store.overview {
                    heroCard(overview: overview)
                    latestIncidentCard(overview.latestIncident)
                    trustPanel(overview: overview)
                } else {
                    ProgressView("Loading EyeQ")
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.top, 60)
                }
            }
            .padding()
        }
        .background(EyeQPalette.canvas.ignoresSafeArea())
        .navigationTitle("EyeQ")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Task { await store.refresh() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                }
            }
        }
    }

    @ViewBuilder
    private func heroCard(overview: OverviewResponse) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Current watch")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Spacer()
                StatusPill(label: overview.monitor.watchState.capitalized, color: statusColor(overview.monitor.watchState))
            }

            Text(overview.monitor.running ? "EyeQ is actively watching \(overview.monitor.name)." : "\(overview.monitor.name) is offline.")
                .font(.title2.weight(.semibold))
                .foregroundStyle(EyeQPalette.ink)

            Text(overview.monitor.lastClassifierReason)
                .font(.body)
                .foregroundStyle(EyeQPalette.subtleInk)

            HStack(spacing: 12) {
                MetricChip(title: "People", value: "\(overview.monitor.peopleCount)")
                MetricChip(title: "Latency", value: "\(overview.monitor.lastReviewLatencyMs) ms")
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(EyeQPalette.card)
                .shadow(color: EyeQPalette.shadow, radius: 20, x: 0, y: 10)
        )
    }

    @ViewBuilder
    private func latestIncidentCard(_ incident: Incident?) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Latest incident")
                    .font(.headline)
                Spacer()
                if let incident {
                    StatusPill(label: incident.status.capitalized, color: statusColor(incident.status))
                }
            }

            if let incident {
                IncidentPreview(incident: incident, compact: false) {
                    store.selectIncident(incident)
                }
            } else {
                Text("No suspicious incidents have been logged yet.")
                    .foregroundStyle(.secondary)
            }
        }
        .padding(20)
        .background(RoundedRectangle(cornerRadius: 28, style: .continuous).fill(Color.white.opacity(0.92)))
    }

    @ViewBuilder
    private func trustPanel(overview: OverviewResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("How alerts reach you")
                .font(.headline)
            Label(overview.notificationChannels.pushConfigured ? "Push notifications are configured." : "Push notifications still need APNs setup.", systemImage: "iphone.radiowaves.left.and.right")
        }
        .foregroundStyle(EyeQPalette.ink)
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 28, style: .continuous)
                .fill(EyeQPalette.warmCard)
        )
    }

    private func statusColor(_ status: String) -> Color {
        switch status.lowercased() {
        case "flagged":
            return .red
        case "reviewing":
            return .orange
        case "watching":
            return .green
        case "cleared":
            return .mint
        default:
            return .gray
        }
    }
}

private struct LiveView: View {
    @EnvironmentObject private var store: AppStore
    @State private var refreshTick = 0

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let monitor = store.overview?.monitor {
                    LiveFrameCard(frameURL: monitor.liveFrameURL, refreshTick: $refreshTick)

                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text(monitor.name)
                                .font(.title3.weight(.semibold))
                            Spacer()
                            StatusPill(label: monitor.watchState.capitalized, color: monitor.running ? .green : .gray)
                        }
                        Text(monitor.lastHeuristicReason.replacingOccurrences(of: "_", with: " ").capitalized)
                            .foregroundStyle(.secondary)
                        Text(monitor.lastClassifierReason)
                            .foregroundStyle(EyeQPalette.subtleInk)
                    }
                    .padding(20)
                    .background(RoundedRectangle(cornerRadius: 28, style: .continuous).fill(Color.white.opacity(0.92)))
                } else {
                    ProgressView("Waiting for live monitor")
                        .padding(.top, 50)
                }
            }
            .padding()
        }
        .background(EyeQPalette.canvas.ignoresSafeArea())
        .navigationTitle("Live camera")
        .task {
            while true {
                try? await Task.sleep(for: .seconds(2))
                refreshTick += 1
            }
        }
    }
}

private struct AlertsView: View {
    @EnvironmentObject private var store: AppStore

    var body: some View {
        List {
            ForEach(store.incidents) { incident in
                IncidentPreview(incident: incident, compact: true) {
                    store.selectIncident(incident)
                }
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
        .scrollContentBackground(.hidden)
        .background(EyeQPalette.canvas.ignoresSafeArea())
        .navigationTitle("Alerts")
    }
}

private struct SettingsView: View {
    @EnvironmentObject private var store: AppStore
    @State private var draftServerURL = ""

    var body: some View {
        Form {
            Section("Server") {
                TextField("http://172.23.25.21:8000", text: $draftServerURL)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .autocorrectionDisabled()

                Button("Save API address") {
                    store.saveServerURL(draftServerURL)
                }
            }

            Section("Notifications") {
                HStack {
                    Text("Permission")
                    Spacer()
                    Text(notificationLabel(store.notificationStatus))
                        .foregroundStyle(.secondary)
                }

                HStack {
                    Text("Device")
                    Spacer()
                    Text(store.deviceTokenLabel)
                        .foregroundStyle(.secondary)
                }

                if let overview = store.overview {
                    HStack {
                        Text("Backend push")
                        Spacer()
                        Text(overview.notificationChannels.pushConfigured ? "Configured" : "Not configured")
                            .foregroundStyle(.secondary)
                    }

                    HStack {
                        Text("Registered devices")
                        Spacer()
                        Text("\(overview.notificationChannels.registeredDevices)")
                            .foregroundStyle(.secondary)
                    }
                }

                Button("Enable notifications") {
                    Task { await store.requestNotificationPermission() }
                }

                Button(store.isSendingTestNotification ? "Sending test alert..." : "Send test alert") {
                    Task { await store.sendTestNotification() }
                }
                .disabled(store.isSendingTestNotification)

                if let notificationDebugMessage = store.notificationDebugMessage {
                    Text(notificationDebugMessage)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
            }

            Section("Monitor setup") {
                if let monitor = store.overview?.monitor {
                    LabeledContent("Monitor", value: monitor.name)
                    LabeledContent("Watch state", value: monitor.watchState.capitalized)
                    LabeledContent("People count", value: "\(monitor.peopleCount)")
                } else {
                    Text("Connect the backend to begin monitor setup.")
                }
            }
        }
        .navigationTitle("Settings")
        .onAppear {
            draftServerURL = store.serverURL
        }
    }

    private func notificationLabel(_ status: UNAuthorizationStatus) -> String {
        switch status {
        case .authorized, .provisional, .ephemeral:
            return "Allowed"
        case .denied:
            return "Denied"
        case .notDetermined:
            return "Not asked"
        @unknown default:
            return "Unknown"
        }
    }
}

private struct IncidentPreview: View {
    let incident: Incident
    let compact: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 14) {
                SnapshotThumbnail(url: incident.snapshotURL)
                    .frame(width: compact ? 90 : 110, height: compact ? 70 : 80)

                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Text(incident.monitorName)
                            .font(.headline)
                            .foregroundStyle(EyeQPalette.ink)
                        Spacer()
                        StatusPill(label: incident.status.capitalized, color: statusColor)
                    }
                    Text(incident.reasonShort)
                        .font(.subheadline)
                        .foregroundStyle(EyeQPalette.subtleInk)
                        .multilineTextAlignment(.leading)
                    Text(incident.startedAt.replacingOccurrences(of: "T", with: " ").replacingOccurrences(of: "Z", with: ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(compact ? 8 : 0)
        }
        .buttonStyle(.plain)
    }

    private var statusColor: Color {
        switch incident.status.lowercased() {
        case "flagged":
            return .red
        case "reviewing":
            return .orange
        case "cleared":
            return .mint
        case "timed_out":
            return .yellow
        default:
            return .gray
        }
    }
}

private struct LiveFrameCard: View {
    let frameURL: URL?
    @Binding var refreshTick: Int

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 32, style: .continuous)
                .fill(Color.black.opacity(0.88))

            if let imageURL = refreshedURL {
                AsyncImage(url: imageURL) { phase in
                    switch phase {
                    case .empty:
                        ProgressView().tint(.white)
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                    case .failure:
                        Text("Live frame unavailable")
                            .foregroundStyle(.white.opacity(0.8))
                    @unknown default:
                        EmptyView()
                    }
                }
            } else {
                Text("Start monitoring to see the live room view.")
                    .foregroundStyle(.white.opacity(0.85))
            }
        }
        .frame(height: 260)
        .clipShape(RoundedRectangle(cornerRadius: 32, style: .continuous))
    }

    private var refreshedURL: URL? {
        guard let frameURL else { return nil }
        var components = URLComponents(url: frameURL, resolvingAgainstBaseURL: false)
        let existingItems = components?.queryItems ?? []
        components?.queryItems = existingItems + [URLQueryItem(name: "tick", value: "\(refreshTick)")]
        return components?.url
    }
}

struct SnapshotThumbnail: View {
    let url: URL?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(Color.black.opacity(0.08))

            if let url {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .empty:
                        ProgressView()
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                    case .failure:
                        Image(systemName: "photo")
                            .foregroundStyle(.secondary)
                    @unknown default:
                        EmptyView()
                    }
                }
            } else {
                Image(systemName: "photo")
                    .foregroundStyle(.secondary)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

private struct MetricChip: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.headline)
                .foregroundStyle(EyeQPalette.ink)
        }
        .padding(12)
        .background(EyeQPalette.softCard)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

struct StatusPill: View {
    let label: String
    let color: Color

    var body: some View {
        Text(label)
            .font(.caption.weight(.semibold))
            .padding(.horizontal, 10)
            .padding(.vertical, 6)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}

enum EyeQPalette {
    static let canvas = LinearGradient(
        colors: [Color(red: 0.96, green: 0.95, blue: 0.92), Color(red: 0.89, green: 0.95, blue: 0.92)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    static let card = Color(red: 0.98, green: 0.98, blue: 0.97)
    static let warmCard = Color(red: 0.98, green: 0.93, blue: 0.87)
    static let softCard = Color(red: 0.93, green: 0.95, blue: 0.96)
    static let ink = Color(red: 0.12, green: 0.16, blue: 0.19)
    static let subtleInk = Color(red: 0.31, green: 0.36, blue: 0.39)
    static let shadow = Color.black.opacity(0.08)
}

#Preview {
    ContentView()
        .environmentObject(AppStore())
}
