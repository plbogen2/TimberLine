import json
import os
import unittest
import xml.etree.ElementTree as ET


class TestVersionSync(unittest.TestCase):
    def test_version_matches_manifest_package_and_changelog(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "VERSION"), encoding="utf-8-sig") as f:
            version = f.read().strip()

        self.assertRegex(version, r"^\d+\.\d+\.\d+$")

        with open(os.path.join(root, "TimberLine.manifest"), encoding="utf-8-sig") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["version"], version)

        tree = ET.parse(os.path.join(root, "PackageContents.xml"))
        pkg_root = tree.getroot()
        self.assertEqual(pkg_root.attrib["AppVersion"], version)
        comp = pkg_root.find("./Components/ComponentEntry")
        self.assertIsNotNone(comp)
        self.assertEqual(comp.attrib["Version"], version)

        with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as f:
            self.assertIn(f"## [{version}]", f.read())


if __name__ == "__main__":
    unittest.main()
