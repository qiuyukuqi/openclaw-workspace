import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/models.dart';
import '../services/api_service.dart';
import '../services/settings_service.dart';

class MonitorViewModel extends ChangeNotifier {
  final _settings = SettingsService();
  ApiService? _api;
  final Map<String, DeviceData> _deviceData = {};
  Timer? _timer;
  bool _loading = false;
  String? _error;

  bool get loading => _loading;
  String? get error => _error;
  DeviceData? get device347 => _deviceData['TSP_347'];
  DeviceData? get device346 => _deviceData['TSP_346'];

  Future<void> init() async {
    _api = ApiService(_settings.apiBase);
    await _api!.login(_settings.account, _settings.password);
    await refresh();
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(Duration(seconds: _settings.refreshInterval), (_) => refresh());
  }

  Future<void> refresh() async {
    _loading = true;
    _error = null;
    notifyListeners();
    try {
      for (final d in devices) {
        final history = await _api!.queryHistory(d.code, pageSize: 100);
        final sorted = history.toList()..sort((a, b) => b.time.compareTo(a.time));
        double? latest;
        DateTime? latestTime;
        DeviceStatus status = DeviceStatus.offline;

        if (sorted.isNotEmpty) {
          latest = sorted.first.tsp;
          latestTime = sorted.first.time;
          final diff = DateTime.now().difference(latestTime);
          if (diff.inMinutes > 30) {
            status = DeviceStatus.interrupted;
          } else if (latest > _settings.threshold) {
            status = DeviceStatus.exceeded;
          } else {
            status = DeviceStatus.normal;
          }
        }

        _deviceData[d.code] = DeviceData(
          code: d.code,
          tsp: latest,
          dataTime: latestTime,
          status: status,
          history: sorted.reversed.toList(),
        );
      }
    } catch (e) {
      _error = e.toString();
    }
    _loading = false;
    notifyListeners();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
