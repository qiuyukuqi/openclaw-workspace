import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:intl/intl.dart';
import '../models/models.dart';
import '../viewmodels/monitor_viewmodel.dart';
import '../services/settings_service.dart';

class MonitorTab extends StatefulWidget {
  const MonitorTab({super.key});
  @override
  State<MonitorTab> createState() => _MonitorTabState();
}

class _MonitorTabState extends State<MonitorTab> {
  bool _show24h = false;

  Color statusColor(DeviceStatus s) => switch (s) {
    DeviceStatus.normal => const Color(0xFFA6E3A1),
    DeviceStatus.exceeded => const Color(0xFF89B4FA),
    DeviceStatus.interrupted => const Color(0xFFFAB387),
    DeviceStatus.offline => const Color(0xFFF38BA8),
  };

  String statusText(DeviceStatus s) => switch (s) {
    DeviceStatus.normal => '正常',
    DeviceStatus.exceeded => '超标',
    DeviceStatus.interrupted => '数据中断',
    DeviceStatus.offline => '离线',
  };

  IconData statusIcon(DeviceStatus s) => switch (s) {
    DeviceStatus.normal => Icons.check_circle,
    DeviceStatus.exceeded => Icons.warning,
    DeviceStatus.interrupted => Icons.sync_problem,
    DeviceStatus.offline => Icons.cancel,
  };

  @override
  Widget build(BuildContext context) {
    final vm = context.watch<MonitorViewModel>();
    final threshold = SettingsService().threshold;

    return RefreshIndicator(
      onRefresh: vm.refresh,
      child: ListView(
        padding: const EdgeInsets.all(12),
        children: [
          // Overall status
          _buildStatusBar(vm),
          const SizedBox(height: 12),
          // Device cards
          _buildDeviceCard(vm.device347, '可逆皮带', threshold),
          const SizedBox(height: 10),
          _buildDeviceCard(vm.device346, '给煤机皮带', threshold),
          const SizedBox(height: 16),
          // Trend chart
          _buildChart(vm, threshold),
          const SizedBox(height: 16),
          // Recent data table
          _buildDataTable(vm),
        ],
      ),
    );
  }

  Widget _buildStatusBar(MonitorViewModel vm) {
    final all = [vm.device347, vm.device346];
    final worst = all.where((d) => d != null).fold<DeviceStatus>(
      DeviceStatus.normal, (a, b) => b!.status.index > a.index ? b.status : a);
    final color = statusColor(worst);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withOpacity(0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        children: [
          Icon(statusIcon(worst), color: color, size: 28),
          const SizedBox(width: 10),
          Text('系统状态: ${statusText(worst)}',
            style: TextStyle(color: color, fontSize: 16, fontWeight: FontWeight.w600)),
          const Spacer(),
          if (vm.loading) const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
        ],
      ),
    );
  }

  Widget _buildDeviceCard(DeviceData? data, String name, double threshold) {
    final color = data != null ? statusColor(data.status) : const Color(0xFFF38BA8);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.sensors, color: color),
              const SizedBox(width: 8),
              Text(name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(statusText(data?.status ?? DeviceStatus.offline),
                  style: TextStyle(color: color, fontSize: 12)),
              ),
            ]),
            const SizedBox(height: 12),
            Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
              Text(data?.tsp?.toStringAsFixed(1) ?? '--', style: TextStyle(
                fontSize: 40, fontWeight: FontWeight.bold, color: color)),
              const SizedBox(width: 4),
              const Padding(padding: EdgeInsets.only(bottom: 8), child: Text('mg/m³', style: TextStyle(color: Color(0xFF6C7086)))),
              const Spacer(),
              Text('阈值: ${threshold.toInt()}', style: const TextStyle(color: Color(0xFF6C7086), fontSize: 13)),
            ]),
            if (data?.dataTime != null)
              Padding(padding: const EdgeInsets.only(top: 4),
                child: Text('更新: ${DateFormat('HH:mm:ss').format(data!.dataTime!)}',
                  style: const TextStyle(color: Color(0xFF6C7086), fontSize: 12))),
          ],
        ),
      ),
    );
  }

  Widget _buildChart(MonitorViewModel vm, double threshold) {
    final data = _show24h ? (vm.device347?.history ?? []) : (vm.device347?.history.take(60).toList() ?? []);
    if (data.isEmpty) return const Card(child: Center(child: Padding(padding: EdgeInsets.all(24), child: Text('暂无数据', style: TextStyle(color: Color(0xFF6C7086))))));

    return Card(
      child: Padding(padding: const EdgeInsets.all(12), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Text('趋势曲线', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
            const Spacer(),
            SegmentedButton<bool>(
              segments: const [ButtonSegment(value: false, label: Text('60分钟')), ButtonSegment(value: true, label: Text('24小时'))],
              selected: {_show24h},
              onSelectionChanged: (s) => setState(() => _show24h = s.first),
              style: const ButtonStyle(visualDensity: VisualDensity.compact, textStyle: MaterialStatePropertyAll(TextStyle(fontSize: 12))),
            ),
          ]),
          const SizedBox(height: 12),
          SizedBox(height: 220, child: LineChart(LineChartData(
            gridData: FlGridData(show: true, drawVerticalLine: false,
              getDrawingHorizontalLine: (v) => const FlLine(color: Color(0xFF45475A), strokeWidth: 0.5)),
            titlesData: FlTitlesData(
              leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 40, getTitlesWidget: (v, _) => Text(v.toInt().toString(), style: const TextStyle(color: Color(0xFF6C7086), fontSize: 10)))),
              bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 24, getTitlesWidget: (v, _) {
                final i = v.toInt();
                if (i < 0 || i >= data.length) return const SizedBox();
                return Padding(padding: const EdgeInsets.only(top: 4), child: Text(DateFormat('HH:mm').format(data[i].time), style: const TextStyle(color: Color(0xFF6C7086), fontSize: 9)));
              }, interval: (data.length / 6).ceilToDouble())),
              rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            ),
            borderData: FlBorderData(show: false),
            lineBarsData: [
              LineChartBarData(
                spots: data.asMap().entries.map((e) => FlSpot(e.key.toDouble(), e.value.tsp)).toList(),
                isCurved: true,
                color: const Color(0xFF89B4FA),
                barWidth: 2,
                dotData: const FlDotData(show: false),
                belowBarData: BarAreaData(show: true, color: const Color(0xFF89B4FA).withOpacity(0.1)),
              ),
              // Threshold line
              LineChartBarData(
                spots: [FlSpot(0, threshold), FlSpot((data.length - 1).toDouble(), threshold)],
                isCurved: false,
                color: const Color(0xFFF38BA8),
                barWidth: 1.5,
                dotData: const FlDotData(show: false),
                dashArray: [6, 4],
              ),
            ],
            minY: 0,
          ))),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Container(width: 20, height: 2, color: const Color(0xFF89B4FA)),
            const SizedBox(width: 4),
            const Text('TSP值', style: TextStyle(color: Color(0xFF6C7086), fontSize: 11)),
            const SizedBox(width: 16),
            Container(width: 20, height: 2, color: const Color(0xFFF38BA8)),
            const SizedBox(width: 4),
            Text('阈值 ${threshold.toInt()}', style: const TextStyle(color: Color(0xFF6C7086), fontSize: 11)),
          ]),
        ],
      ))),
    );
  }

  Widget _buildDataTable(MonitorViewModel vm) {
    final data = (vm.device347?.history ?? []).reversed.take(10).toList();
    if (data.isEmpty) return const SizedBox();
    return Card(
      child: Padding(padding: const EdgeInsets.all(12), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('最近数据 (TSP_347)', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Table(columnWidths: const {0: FlexColumnWidth(3), 1: FlexColumnWidth(2)},
            defaultVerticalAlignment: TableCellVerticalAlignment.middle,
            children: [
              const TableRow(decoration: BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFF45475A)))),
                children: [Padding(padding: EdgeInsets.symmetric(vertical: 6), child: Text('时间', style: TextStyle(color: Color(0xFF6C7086), fontSize: 12))),
                  Padding(padding: EdgeInsets.symmetric(vertical: 6), child: Text('TSP (mg/m³)', style: TextStyle(color: Color(0xFF6C7086), fontSize: 12)))]),
              ...data.map((d) => TableRow(decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: Color(0xFF45475A), width: 0.5))),
                children: [
                  Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(DateFormat('MM-dd HH:mm').format(d.time), style: const TextStyle(fontSize: 12))),
                  Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(d.tsp.toStringAsFixed(1),
                    style: TextStyle(fontSize: 12, color: d.tsp > SettingsService().threshold ? const Color(0xFFF38BA8) : const Color(0xFFA6E3A1))))])),
            ],
          ),
        ],
      )),
    );
  }
}
