import AVKit
import SwiftUI

struct IncidentDetailView: View {
    let incident: Incident

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let clipURL = incident.clipURL, incident.clipReady {
                        VideoPlayer(player: AVPlayer(url: clipURL))
                            .frame(height: 240)
                            .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
                    } else {
                        SnapshotThumbnail(url: incident.snapshotURL)
                            .frame(height: 220)
                    }

                    VStack(alignment: .leading, spacing: 12) {
                        HStack {
                            Text(incident.monitorName)
                                .font(.title3.weight(.semibold))
                            Spacer()
                            StatusPill(label: incident.status.capitalized, color: statusColor)
                        }

                        Text(incident.reasonShort)
                            .font(.title2.weight(.semibold))
                            .foregroundStyle(CareWatchPalette.ink)

                        DetailRow(title: "Started", value: incident.startedAt)
                        DetailRow(title: "Severity", value: incident.severity.capitalized)
                        DetailRow(title: "Review latency", value: "\(incident.reviewLatencyMs) ms")
                        DetailRow(title: "Heuristic", value: incident.heuristicReason)
                        DetailRow(title: "Decision", value: incident.classifierReason)

                        if !incident.suggestedAction.isEmpty {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("Suggested action")
                                    .font(.headline)
                                Text(incident.suggestedAction)
                                    .foregroundStyle(CareWatchPalette.subtleInk)
                            }
                            .padding(.top, 8)
                        }
                    }
                    .padding(20)
                    .background(RoundedRectangle(cornerRadius: 28, style: .continuous).fill(Color.white.opacity(0.92)))
                }
                .padding()
            }
            .background(CareWatchPalette.canvas.ignoresSafeArea())
            .navigationTitle("Incident")
            .navigationBarTitleDisplayMode(.inline)
        }
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

private struct DetailRow: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
            Text(value.isEmpty ? "Unavailable" : value)
                .foregroundStyle(CareWatchPalette.ink)
        }
    }
}
