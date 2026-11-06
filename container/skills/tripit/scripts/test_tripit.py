import io, json, os, sys, unittest, urllib.error
sys.path.insert(0, os.path.dirname(__file__))
import tripit_cli as tc


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


class T(unittest.TestCase):
    def run_cli(self, argv, routes, stdin=None):
        seen, out, err = [], io.StringIO(), io.StringIO()

        def opener(req, timeout=None):
            seen.append((req.get_method(), req.full_url.split("/tripit")[1], json.loads(req.data) if req.data else None, dict(req.headers)))
            for key, body in routes.items():
                if req.full_url.split("/tripit")[1].startswith(key):
                    if isinstance(body, tuple):
                        raise urllib.error.HTTPError(req.full_url, body[0], "x", {}, io.BytesIO(json.dumps({"detail": body[1]}).encode()))
                    return Resp(json.dumps(body).encode())
            raise AssertionError(req.full_url)
        real = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr = out, err
        if stdin is not None:
            sys.stdin = io.StringIO(stdin)
        try:
            code = tc.main(argv, opener=opener)
        finally:
            sys.stdout, sys.stderr, sys.stdin = real
        return code, out.getvalue(), err.getvalue(), seen

    def test_trips_summary_handles_one_or_many(self):
        many = {"result": {"Trip": [{"uuid": "u1", "display_name": "NZ", "start_date": "2027-01-04", "end_date": "2027-01-20", "primary_location": "Auckland"},
                                    {"id": "u2", "displayName": "Mornington", "startDate": "2026-10-11", "endDate": "2026-10-14"}]}}
        code, out, _, seen = self.run_cli(["trips"], {"/call": many})
        self.assertEqual(code, 0)
        self.assertIn("u1 | NZ | 2027-01-04 to 2027-01-20 | Auckland", out)
        self.assertIn("u2 | Mornington", out)
        self.assertEqual(seen[0][2], {"kind": "trips", "verb": "list", "data": {"past": False}})
        self.assertNotIn("X-api-key", seen[0][3])               # the gateway adds it, never this script
        _, one, _, _ = self.run_cli(["trips"], {"/call": {"result": {"Trip": {"uuid": "u9", "display_name": "Solo"}}}})
        self.assertIn("1 trip(s)", one)
        _, none, _, _ = self.run_cli(["trips"], {"/call": {"result": {}}})
        self.assertEqual(none.strip(), "No trips.")

    def test_create_sends_the_json_and_stdin_works(self):
        code, out, _, seen = self.run_cli(["create", "hotels", '{"tripId":"t","hotelName":"H"}'], {"/call": {"result": {"ok": 1}}})
        self.assertEqual(seen[0][2], {"kind": "hotels", "verb": "create", "data": {"tripId": "t", "hotelName": "H"}})
        _, _, _, seen2 = self.run_cli(["update", "trips", "-"], {"/call": {"result": {}}}, stdin='{"id":"abc123","displayName":"X"}')
        self.assertEqual(seen2[0][2]["data"]["id"], "abc123")

    def test_success_line_uses_the_right_singular(self):
        for kind, word in (("activities", "activity"), ("transport", "transport"), ("hotels", "hotel"), ("trips", "trip")):
            _, out, _, _ = self.run_cli(["create", kind, '{"tripId":"t"}'], {"/call": {"result": {}}})
            self.assertTrue(out.startswith(f"created {word}:"), out)

    def test_bad_json_never_reaches_the_bridge(self):
        code, _, err, seen = self.run_cli(["create", "trips", "{nope"], {})
        self.assertEqual((code, seen), (2, []))
        self.assertIn("not valid JSON", err)

    def test_delete_is_two_steps_and_says_so(self):
        req = {"code": "AB12CD", "expiresInMinutes": 30, "preview": {"name": "Hobbiton tour"}}
        code, out, _, seen = self.run_cli(["delete", "activities", "abcdef"], {"/delete/request": req})
        self.assertIn("NOT DELETED YET", out)
        self.assertIn("delete-confirm AB12CD", out)
        self.assertEqual([s[1] for s in seen], ["/delete/request"])
        code, out, _, seen = self.run_cli(["delete-confirm", "AB12CD"], {"/delete/confirm": {"deleted": True, "kind": "activities", "id": "abcdef"}})
        self.assertIn("deleted activities abcdef", out)

    def test_errors_are_explained(self):
        code, _, err, _ = self.run_cli(["trips"], {"/call": (403, "Invalid API key")})
        self.assertEqual(code, 2)
        self.assertIn("OneCLI", err)
        code, _, err, _ = self.run_cli(["trips"], {"/call": (503, "TripIt login is not configured")})
        self.assertIn("not configured", err)
        def down(req, timeout=None): raise urllib.error.URLError("refused")
        out, e = io.StringIO(), io.StringIO()
        real = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = out, e
        try:
            code = tc.main(["trips"], opener=down)
        finally:
            sys.stdout, sys.stderr = real
        self.assertEqual(code, 2)
        self.assertIn("cannot reach", e.getvalue())

    def test_trip_summary_lists_each_booking_in_one_line(self):
        trip = {"Trip": {"uuid": "T1", "display_name": "NZ", "start_date": "2027-03-10", "end_date": "2027-03-12", "primary_location": "Auckland"},
                "AirObject": {"uuid": "A1", "display_name": "Flight", "Segment": [{"StartDateTime": {"date": "2027-03-10", "time": "08:00:00"}, "EndDateTime": {"date": "2027-03-10", "time": "13:30:00"},
                              "start_city_name": "Sydney", "end_city_name": "Auckland"}]},
                "LodgingObject": [{"uuid": "H1", "display_name": "Hotel", "supplier_conf_num": "C9", "StartDateTime": {"date": "2027-03-10"}, "EndDateTime": {"date": "2027-03-12"},
                                   "Address": {"address": "1 Queen St", "city": "Auckland"}}],
                "ActivityObject": {"uuid": "X1", "display_name": "Sky Tower", "StartDateTime": {"date": "2027-03-11", "time": "10:00:00"}}}
        code, out, _, _ = self.run_cli(["get", "trips", "T1"], {"/call": {"result": trip}})
        self.assertIn("NZ | 2027-03-10 to 2027-03-12 | Auckland | id T1", out)
        self.assertIn("flight | A1 | Flight | 2027-03-10 08:00 to 2027-03-10 13:30 | Sydney to Auckland", out)
        self.assertIn("hotel | H1 | Hotel | 2027-03-10 to 2027-03-12 | 1 Queen St, Auckland | conf C9", out)
        self.assertIn("activity | X1 | Sky Tower", out)
        trip["TransportObject"] = {"uuid": "R1", "display_name": "Drive", "Segment": {"StartDateTime": {"date": "2027-03-10", "time": "09:00:00"}, "EndDateTime": {"date": "2027-03-10", "time": "12:30:00"},
                                   "start_location_name": "Sydney (home)", "end_location_name": "The Sebel"}}
        _, out2, _, _ = self.run_cli(["get", "trips", "T1"], {"/call": {"result": trip}})
        self.assertIn("transport | R1 | Drive | 2027-03-10 09:00 to 2027-03-10 12:30 | Sydney (home) to The Sebel", out2)
        _, empty, _, _ = self.run_cli(["get", "trips", "T2"], {"/call": {"result": {"Trip": {"uuid": "T2", "display_name": "Empty"}}}})
        self.assertIn("(no bookings yet)", empty)
        _, raw, _, _ = self.run_cli(["get", "trips", "T1", "--json"], {"/call": {"result": trip}})
        self.assertIn('"AirObject"', raw)

    def test_changes_listing(self):
        code, out, _, _ = self.run_cli(["changes"], {"/changes": {"changes": [{"at": "2026-11-07T01:00:00Z", "verb": "create", "kind": "trips", "label": "NZ"}]}})
        self.assertIn("2026-11-07T01:00 create trips NZ", out)


if __name__ == "__main__":
    unittest.main()
