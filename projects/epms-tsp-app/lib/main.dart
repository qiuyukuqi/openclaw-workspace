import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_service.dart';
import 'services/settings_service.dart';
import 'viewmodels/monitor_viewmodel.dart';
import 'views/main_tab_view.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SettingsService().init();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'EPMS TSP 监控',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF1E1E2E),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF89B4FA),
          secondary: Color(0xFFA6E3A1),
          surface: Color(0xFF313244),
          error: Color(0xFFF38BA8),
        ),
        cardTheme: CardThemeData(
          color: const Color(0xFF313244),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFF1E1E2E),
          foregroundColor: Colors.white,
        ),
        tabBarTheme: const TabBarTheme(
          labelColor: Color(0xFF89B4FA),
          unselectedLabelColor: Color(0xFF6C7086),
        ),
      ),
      home: ChangeNotifierProvider(
        create: (_) => MonitorViewModel(),
        child: const MainTabView(),
      ),
    );
  }
}
