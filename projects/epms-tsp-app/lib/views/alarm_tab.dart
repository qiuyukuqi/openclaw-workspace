import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/models.dart';
import '../services/settings_service.dart';

class AlarmTab extends StatefulWidget {
  const AlarmTab({super.key});
  @override
  State<AlarmTab> createState() => _AlarmTabState();
}

class _AlarmTabState extends State<AlarmTab> {
  String _filterDevice = '全部';
  String _filterType = '全部';
  List<AlarmRecord> _alarms = [];

  @override
  void initState() {
    super.initState();
    _loadAlarms();
  }

  Future<void> _loadAlarms() async {
    final db = await SettingsService().db;
    final list = await db.query('alarms', orderBy: 'time DESC');
    setState(() => _alarms = list.map((m) => AlarmRecord.fromMap(m)).toList());
  }

  List<AlarmRecord> get _filtered => _alarms.where((a) {
    if (_filterDevice != '全部' && a.deviceCode != _filterDevice) return false;
    if (_filterType != '全部' && a.alarmType != _filterType) return false;
    return true;
  }).toList();

  Color _typeColor(String t) => switch (t) {
    'exceeded' => const Color(0xFF89B4FA),
    'interrupted' => const Color(0xFFFAB387),
    'offline' => const Color(0xFFF38BA8),
    _ => const Color(0xFF6C7086),
  };

  String _typeName(String t) => switch (t) {
    'exceeded' => '超标',
    'interrupted' => '中断',
    'offline' => '离线',
    _ => t,
  };

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      Padding(padding: const EdgeInsets.all(12), child: Row(children: [
        Expanded(child: DropdownButtonFormField<String>(
          value: _filterDevice, decoration: const InputDecoration(labelText: '设备', isDense: true),
          items: ['全部', 'TSP_347', 'TSP_346'].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
          onChanged: (v) => setState(() => _filterDevice = v ?? '全部'))),
        const SizedBox(width: 8),
        Expanded(child: DropdownButtonFormField<String>(
          value: _filterType, decoration: const InputDecoration(labelText: '类型', isDense: true),
          items: ['全部', 'exceeded', 'interrupted', 'offline'].map((v) => DropdownMenuItem(value: v, child: Text(v == '全部' ? '全部' : _typeName(v)))).toList(),
          onChanged: (v) => setState(() => _filterType = v ?? '全部'))),
      ])),
      Expanded(child: _filtered.isEmpty
        ? const Center(child: Text('暂无告警记录', style: TextStyle(color: Color(0xFF6C7086))))
        : ListView.builder(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: _filtered.length,
            itemBuilder: (ctx, i) {
              final a = _filtered[i];
              return Card(margin: const EdgeInsets.only(bottom: 6), child: ListTile(
                leading: Icon(Icons.warning_amber, color: _typeColor(a.alarmType)),
                title: Text(a.message, style: const TextStyle(fontSize: 13)),
                subtitle: Text('${a.deviceCode} · ${DateFormat('MM-dd HH:mm:ss').format(a.time)}', style: const TextStyle(color: Color(0xFF6C7086), fontSize: 11)),
                trailing: Container(padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(color: _typeColor(a.alarmType).withOpacity(0.2), borderRadius: BorderRadius.circular(8)),
                  child: Text(_typeName(a.alarmType), style: TextStyle(color: _typeColor(a.alarmType), fontSize: 11))),
              ));
            })),
    ]);
  }
}
