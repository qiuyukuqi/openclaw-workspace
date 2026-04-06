import 'package:flutter/material.dart';
import '../services/settings_service.dart';
import '../services/api_service.dart';
import 'package:provider/provider.dart';
import '../viewmodels/monitor_viewmodel.dart';

class SettingsTab extends StatefulWidget {
  const SettingsTab({super.key});
  @override
  State<SettingsTab> createState() => _SettingsTabState();
}

class _SettingsTabState extends State<SettingsTab> {
  late TextEditingController _apiController;
  late TextEditingController _intervalController;
  late TextEditingController _thresholdController;
  bool _notifications = true;

  @override
  void initState() {
    super.initState();
    final s = SettingsService();
    _apiController = TextEditingController(text: s.apiBase);
    _intervalController = TextEditingController(text: s.refreshInterval.toString());
    _thresholdController = TextEditingController(text: s.threshold.toString());
    _notifications = s.notificationsEnabled;
  }

  void _save() {
    final s = SettingsService();
    s.apiBase = _apiController.text;
    s.refreshInterval = int.tryParse(_intervalController.text) ?? 10;
    s.threshold = double.tryParse(_thresholdController.text) ?? 400;
    s.notificationsEnabled = _notifications;
    context.read<MonitorViewModel>().init();
    ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('设置已保存')));
  }

  @override
  Widget build(BuildContext context) {
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('API 配置', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      TextField(controller: _apiController, decoration: const InputDecoration(labelText: 'API 地址', hintText: 'http://xxx:port')),
      const SizedBox(height: 16),
      const Text('监控设置', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
      const SizedBox(height: 8),
      TextField(controller: _intervalController, decoration: const InputDecoration(labelText: '刷新间隔(秒)'), keyboardType: TextInputType.number),
      const SizedBox(height: 8),
      TextField(controller: _thresholdController, decoration: const InputDecoration(labelText: '阈值(mg/m³)'), keyboardType: TextInputType.number),
      const SizedBox(height: 16),
      SwitchListTile(title: const Text('推送通知'), subtitle: const Text('超标/中断/离线时通知'),
        value: _notifications, onChanged: (v) => setState(() => _notifications = v)),
      const SizedBox(height: 24),
      FilledButton(onPressed: _save, child: const Text('保存设置')),
      const SizedBox(height: 16),
      OutlinedButton(onPressed: () async {
        final api = ApiService(_apiController.text);
        final ok = await api.login(SettingsService().account, SettingsService().password);
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(ok ? '连接成功' : '连接失败')));
      }, child: const Text('测试连接')),
    ]);
  }
}
