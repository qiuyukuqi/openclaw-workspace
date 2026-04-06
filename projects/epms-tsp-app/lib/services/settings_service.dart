import 'package:shared_preferences/shared_preferences.dart';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

class SettingsService {
  static final SettingsService _instance = SettingsService._();
  factory SettingsService() => _instance;
  SettingsService._();

  late SharedPreferences _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
    await _initDb();
  }

  String get apiBase => _prefs.getString('api_base') ?? 'http://60.164.184.43:17641';
  set apiBase(String v) => _prefs.setString('api_base', v);

  int get refreshInterval => _prefs.getInt('refresh_interval') ?? 10;
  set refreshInterval(int v) => _prefs.setInt('refresh_interval', v);

  double get threshold => _prefs.getDouble('threshold') ?? 400;
  set threshold(double v) => _prefs.setDouble('threshold', v);

  bool get notificationsEnabled => _prefs.getBool('notifications') ?? true;
  set notificationsEnabled(bool v) => _prefs.setBool('notifications', v);

  String get account => _prefs.getString('account') ?? '00008323';
  String get password => _prefs.getString('password') ?? 'df66717d95cbcea8e2fe13ef3ed23b21';

  // SQLite for alarms
  static Database? _db;

  Future<Database> get db async {
    _db ??= await _initDb();
    return _db!;
  }

  Future<Database> _initDb() async {
    final path = join(await getDatabasesPath(), 'epms_tsp.db');
    return openDatabase(path, version: 1, onCreate: (db, v) async {
      await db.execute('''CREATE TABLE alarms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deviceCode TEXT,
        alarmType TEXT,
        value REAL,
        time TEXT,
        message TEXT
      )''');
    });
  }
}
