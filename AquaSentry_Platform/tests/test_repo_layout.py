"""Repository layout guards (v5.7 clean-up).

1. Files kept in more than one place on purpose (so each part runs on its own) must stay byte-identical.
2. Every relative link in the documentation must point at a file or folder that exists.
3. No documentation links into someone's own computer (file:///Users/...).

Skipped when the tests run without the full repository (for example inside the Docker image, which leaves out Docs/).
"""
import filecmp
import os
import re
import unittest

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(PLATFORM)
FULL_REPO = all(os.path.isdir(os.path.join(REPO, d)) for d in ("Docs", "Neural_Network", "Firmware"))

# (canonical, copy) pairs. The first file is the one to edit; copy it over the others.
COPIES = [
    ("Neural_Network/aquanet_v1.c", "Firmware/esp32_firmware/aquanet_v1.c"),
    ("Neural_Network/aquanet_v1.h", "Firmware/esp32_firmware/aquanet_v1.h"),
    ("Neural_Network/aquanet_v3.py", "AquaSentry_Platform/app/aquanet_v3.py"),
    ("Neural_Network/aquanet_v3_weights.json", "AquaSentry_Platform/app/aquanet_v3_weights.json"),
    ("Neural_Network/aquanet_v2_weights.json", "AquaSentry_Platform/app/aquanet_v2_weights.json"),
    ("Data/example_data.csv", "AquaSentry_Platform/data/example_data.csv"),
    ("Data/example_data.csv", "Neural_Network/example_data.csv"),
    ("Data/calibration.json", "AquaSentry_Platform/data/calibration.json"),
    ("Data/calibration.json", "Neural_Network/calibration.json"),
    ("Data/example_calibration.json", "AquaSentry_Platform/data/example_calibration.json"),
    ("Data/arsenic_voltammetry_example.csv", "AquaSentry_Platform/data/arsenic_voltammetry_example.csv"),
    ("Data/voltammetry2_arsenic_example.csv", "AquaSentry_Platform/data/voltammetry2_arsenic_example.csv"),
    ("Docs/hardware/catamaran_prototype_render.jpg", "AquaSentry_Platform/frontend/catamaran_prototype_render.jpg"),
    ("Docs/hardware/personal_tank_prototype_render.jpg", "AquaSentry_Platform/frontend/personal_tank_prototype_render.jpg"),
]

LINK = re.compile(r"\]\(([^)\s]+)\)")
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", ".pytest_cache", ".ruff_cache"}


def _markdown_files():
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel_root = os.path.relpath(root, REPO).replace(os.sep, "/")
        if rel_root.startswith("Docs/archive"):     # kept word for word; old paths are expected there
            continue
        for f in files:
            if f.endswith(".md"):
                yield os.path.join(root, f)


@unittest.skipUnless(FULL_REPO, "needs the full repository")
class RepoLayoutTests(unittest.TestCase):
    def test_copies_identical(self):
        for a, b in COPIES:
            pa, pb = os.path.join(REPO, a), os.path.join(REPO, b)
            self.assertTrue(os.path.isfile(pa), a)
            self.assertTrue(os.path.isfile(pb), b)
            self.assertTrue(filecmp.cmp(pa, pb, shallow=False), f"{b} differs from {a}: copy {a} over it")

    def test_relative_doc_links_resolve(self):
        broken = []
        for md in _markdown_files():
            text = open(md, encoding="utf-8").read()
            text = re.sub(r"```.*?```", "", text, flags=re.S)        # ignore code blocks
            for target in LINK.findall(text):
                if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
                    continue                                          # http:, mailto:, in-page anchors
                path = target.split("#", 1)[0]
                if not path:
                    continue
                if not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(md), path))):
                    broken.append(f"{os.path.relpath(md, REPO)} -> {target}")
        self.assertEqual(broken, [], "broken documentation links:\n" + "\n".join(broken))

    def test_no_links_to_personal_computers(self):
        bad = [os.path.relpath(md, REPO) for md in _markdown_files() if "](file:///" in open(md, encoding="utf-8").read()]
        self.assertEqual(bad, [])

    def test_launchers_in_scripts_reach_the_repo_root(self):
        for name in ("setup_and_run.sh", "run_all_tests.sh"):
            self.assertIn('cd "$SCRIPT_DIR/.."', open(os.path.join(REPO, "scripts", name), encoding="utf-8").read(), name)
        for name in ("setup_and_run.bat", "run_all_tests.bat", "build_desktop_exe.bat"):
            self.assertIn('cd /d "%~dp0.."', open(os.path.join(REPO, "scripts", name), encoding="utf-8").read(), name)


if __name__ == "__main__":
    unittest.main()
