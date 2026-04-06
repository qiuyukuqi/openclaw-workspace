import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'monitor_tab.dart';
import 'alarm_tab.dart';
import 'report_tab.dart';
import 'settings_tab.dart';

class MainTabView extends StatefulWidget {
  const MainTabView({super.key});

  @override
  State<MainTabView> createState() => _MainTabViewState();
}

class _MainTabViewState extends State<MainTabView> with SingleTickerProviderStateMixin {
  late TabController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TabController(length: 4, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<MonitorViewModel>().init();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('EPMS TSP 监控', style: TextStyle(fontWeight: FontWeight.bold)),
        bottom: TabBar(
          controller: _controller,
          tabs: const [
            Tab(text: '实时监控', icon: Icon(Icons.monitor_heart_outlined)),
            Tab(text: '告警', icon: Icon(Icons.warning_amber_outlined)),
            Tab(text: '报表', icon: Icon(Icons.table_chart_outlined)),
            Tab(text: '设置', icon: Icon(Icons.settings_outlined)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _controller,
        children: const [
          MonitorTab(),
          AlarmTab(),
          ReportTab(),
          SettingsTab(),
        ],
      ),
    );
  }
}
