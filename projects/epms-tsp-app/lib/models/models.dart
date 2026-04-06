class DeviceInfo {
  final String code;
  final String name;
  final double threshold;

  const DeviceInfo({required this.code, required this.name, required this.threshold});
}

class DeviceData {
  final String code;
  final double? tsp;
  final DateTime? dataTime;
  final DeviceStatus status;
  final List<HistoryPoint> history;

  DeviceData({
    required this.code,
    this.tsp,
    this.dataTime,
    this.status = DeviceStatus.offline,
    this.history = const [],
  });
}

enum DeviceStatus { normal, exceeded, interrupted, offline }

class HistoryPoint {
  final DateTime time;
  final double tsp;
  HistoryPoint({required this.time, required this.tsp});
}

class AlarmRecord {
  int? id;
  final String deviceCode;
  final String alarmType; // exceeded, interrupted, offline
  final double? value;
  final DateTime time;
  final String message;

  AlarmRecord({
    this.id,
    required this.deviceCode,
    required this.alarmType,
    this.value,
    required this.time,
    required this.message,
  });

  Map<String, dynamic> toMap() => {
    'id': id,
    'deviceCode': deviceCode,
    'alarmType': alarmType,
    'value': value,
    'time': time.toIso8601String(),
    'message': message,
  };

  factory AlarmRecord.fromMap(Map<String, dynamic> m) => AlarmRecord(
    id: m['id'],
    deviceCode: m['deviceCode'],
    alarmType: m['alarmType'],
    value: m['value'],
    time: DateTime.parse(m['time']),
    message: m['message'],
  );
}

const devices = [
  DeviceInfo(code: 'TSP_347', name: '可逆皮带', threshold: 400),
  DeviceInfo(code: 'TSP_346', name: '给煤机皮带', threshold: 400),
];
