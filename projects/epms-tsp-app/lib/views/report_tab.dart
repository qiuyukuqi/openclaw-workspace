import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../models/models.dart';
import '../viewmodels/monitor_viewmodel.dart';
import '../services/settings_service.dart';

class ReportTab extends StatefulWidget {
  const ReportTab({super.key});
  @override
  State<ReportTab> createState() => _ReportTabState();
}

class _ReportTabState extends State<ReportTab> {
  String _selectedDevice = 'TSP_347';
  DateTimeRange _dateRange = DateTimeRange(
    start: DateTime.now().subtract(const Duration(hours: 24)),
    end: DateTime.now(),
  );
  bool _loading = false;
  List<HistoryPoint> _data = [];

  Future<void> _query() async {
    setState(() => _loading = true);
    try {
      final api = ApiService(SettingsService().apiBase);
      await api.login(SettingsService().account, SettingsService().password);
      _data = await api.queryHistory(_selectedDevice, pageSize: 500);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('查询失败: $e')));
    }
    setState(() => _loading = false);
  }

  void _exportCsv() {
    if (_data.isEmpty) return;
    final csv = StringBuffer('时间,TSP(mg/m³)\n');
    for (final d in _data) {
      csv.writeln('${DateFormat('yyyy-MM-dd HH:mm:ss').format(d.time)},${d.tsp.toStringAsFixed(1)}');
    }
    // Save via share - simplified: show as text
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text('已生成 ${_data.length} 条数据 (${_selectedDevice})'),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Padding(padding: const EdgeInsets.all(12), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: DropdownButtonFormField<String>(
          value: _selectedDevice,
          decoration: const InputDecoration(labelText: '设备', isDense: true),
          items: ['TSP_347', 'TSP_346'].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
          onChanged: (v) => setState(() => _selectedDevice = v!))),
        const SizedBox(width: 8),
        ElevatedButton(onPressed: _loading ? null : _query, child: const Text('查询')),
        const SizedBox(width: 8),
        OutlinedButton(onPressed: _data.isEmpty ? null : _exportCsv, child: const Text('导出CSV')),
      ]),
      const SizedBox(height: 12),
      if (_loading) const Center(child: CircularProgressIndicator()),
      if (!_loading) Expanded(child: _data.isEmpty
        ? const Center(child: Text('请选择设备并查询', style: TextStyle(color: Color(0xFF6C7086))))
        : SingleChildScrollView(scrollDirection: Axis.vertical, child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: DataTable(
            columns: const [DataColumn(label: Text('时间')), DataColumn(label: Text('TSP (mg/m³)'))],
            rows: _data.map((d) => DataRow(cells: [
              DataCell(Text(DateFormat('MM-dd HH:mm').format(d.time), style: const TextStyle(fontSize: 12))),
              DataCell(Text(d.tsp.toStringAsFixed(1), style: const TextStyle(fontSize: 12))),
            ])).toList(),
          ))),
    ]));
  }
}
