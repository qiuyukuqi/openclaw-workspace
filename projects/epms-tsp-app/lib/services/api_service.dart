import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/models.dart';

class ApiService {
  final String _baseUrl;
  String? _token;

  ApiService(this._baseUrl);

  Future<bool> login(String account, String password) async {
    final resp = await http.post(
      Uri.parse('$_baseUrl/api/base/SysLogin/LoginWithoutCode'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'account': account, 'password': password}),
    );
    final data = jsonDecode(resp.body);
    if (data['ResultType'] == 200) {
      _token = data['Data']['Token'];
      return true;
    }
    return false;
  }

  Future<List<HistoryPoint>> queryHistory(String deviceCode, {int step = 60, int pageSize = 100}) async {
    final resp = await http.post(
      Uri.parse('$_baseUrl/api/EPMS/Emission/History/QueryByPage'),
      headers: {
        'Content-Type': 'application/json',
        'authorization': _token ?? '',
      },
      body: jsonEncode({
        'deviceType': 'tsp',
        'DeviceCode': deviceCode,
        'pageIndex': 1,
        'pageSize': pageSize,
        'step': step,
      }),
    );
    final data = jsonDecode(resp.body);
    if (data['ResultType'] == 200 && data['Data'] != null) {
      final page = data['Data']['Page'] as List? ?? [];
      return page.map((e) => HistoryPoint(
        time: DateTime.parse(e['DataTime']),
        tsp: (e['TSP'] as num).toDouble(),
      )).toList();
    }
    return [];
  }

  String? get token => _token;
}
