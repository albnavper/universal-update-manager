# Universal Update Manager — Audit & Refactor

## Task Checklist

### Critical Tier
- [x] Fix D-Bus variant packing in `tray_runner.py` (on_check_clicked, on_quit_clicked)
- [x] Fix bare `except:` in `main_window.py` (`_create_app_icon`)
- [x] Add `clear_cache()` to `IconResolver`

### High Tier
- [x] Fix bare `except:` in `web_scraper.py` (`_get_text_content`)
- [x] Fix bare `except:` in `snap.py` (`_is_snap_available`)
- [x] Add `pkexec` for `snap refresh` / `snap remove` (root required)
- [x] Fix JetBrains version comparison (string `!=` → `compare_versions`)
- [x] Add missing `download_url` field to `DownloadResult` in `base.py`
- [x] Add thread-safety lock (`threading.Lock`) to `engine.py` `_check_single`

### Medium Tier
- [x] Fix bare `except:` in `scanner.py` (`_detect_opt_version`)
- [x] Hoist `subprocess` import to module level in `main_window.py`
- [x] Add safe `_hide_banner` helper (replaces lambda in GLib.timeout_add)

### Low Tier
- [x] Fix bare `except:` in `notifications.py` (`_check_notify_send`)
- [x] Use `XDG_CONFIG_HOME` in `notifications.py` for history path
- [x] Use `XDG_CACHE_HOME` in `security.py` for backup path
- [x] Use `core.version.is_newer` in `migration.py` (replaces fragile string comparison)
- [x] Add rollback on GitHub install failure in `migration.py`

### Test Suite
- [x] Create `tests/__init__.py`
- [x] Create `tests/test_version.py` (30 tests)
- [x] Create `tests/test_base.py` (15 tests)

### Verification
- [x] All modified source files compile clean (py_compile)
- [x] `main_window.py` AST parses correctly
- [x] All 45 tests pass
