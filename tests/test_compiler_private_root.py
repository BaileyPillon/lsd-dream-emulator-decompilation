"""Private compiler artifacts must not overwrite retained data or enter Git worktrees."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.collision import trace_compiler_stack as tracer


class CompilerPrivateRootTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.checkout = self.base/'checkout'
        self.checkout.mkdir()
        (self.checkout/'.git').mkdir()
        self.private = self.base/'artifact drive'/'private'
        self.private.mkdir(parents=True)
        self.root_patch = patch.object(tracer, 'ROOT', self.checkout)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def test_default_keeps_existing_private_checkout_location(self):
        output = self.checkout/'.decomp-lab'/'new-trace'
        self.assertEqual(tracer.new_output(output), output)
        self.assertTrue(output.is_dir())

    def test_explicit_external_root_supports_spaces_and_nested_runs(self):
        output = self.private/'run with spaces'/'lifetime'
        self.assertEqual(tracer.new_output(output, self.private), output)
        self.assertTrue(output.is_dir())

    def test_explicit_checkout_private_subroot_remains_allowed(self):
        lab = self.checkout/'.decomp-lab'/'storage'
        lab.mkdir(parents=True)
        self.assertEqual(tracer.new_output(lab/'run', lab), lab/'run')

    def test_output_escape_and_private_root_itself_are_rejected(self):
        for output in [self.private, self.private/'..'/'escape', self.base/'public']:
            with self.subTest(output=output), self.assertRaises(ValueError):
                tracer.new_output(output, self.private)
        self.assertFalse((self.base/'public').exists())
        self.assertFalse((self.private.parent/'escape').exists())

    def test_relative_or_missing_roots_are_rejected_before_output_creation(self):
        output = self.base/'unexpected'
        for root in [Path('relative-private'), self.base/'missing']:
            with self.subTest(root=root), self.assertRaises((ValueError, FileNotFoundError)):
                tracer.new_output(output, root)
        self.assertFalse(output.exists())

    def test_checkout_and_its_ancestor_cannot_be_declared_private(self):
        for root in [self.checkout, self.base, Path(self.base.anchor)]:
            with self.subTest(root=root), self.assertRaises(ValueError):
                tracer.new_output(root/'unexpected', root)
        self.assertFalse((self.checkout/'unexpected').exists())

    def test_project_source_directory_cannot_be_declared_private(self):
        root = self.checkout/'research'
        root.mkdir()
        with self.assertRaisesRegex(ValueError, 'under .decomp-lab'):
            tracer.new_output(root/'unexpected', root)
        self.assertFalse((root/'unexpected').exists())

    def test_other_git_directory_and_managed_worktree_file_are_rejected(self):
        for name, directory in [('git-directory', True), ('git-file', False)]:
            git_root = self.base/name
            git_root.mkdir()
            marker = git_root/'.git'
            if directory:
                marker.mkdir()
            else:
                marker.write_text('gitdir: ../shared/worktrees/example\n')
            lab = git_root/'private'
            lab.mkdir()
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'outside Git worktrees'):
                tracer.new_output(lab/'unexpected', lab)
            self.assertFalse((lab/'unexpected').exists())

    def test_nested_git_worktree_under_private_root_is_also_rejected(self):
        nested = self.private/'clone'
        nested.mkdir()
        (nested/'.git').mkdir()
        with self.assertRaisesRegex(ValueError, 'nested Git worktree'):
            tracer.new_output(nested/'unexpected', self.private)
        self.assertFalse((nested/'unexpected').exists())

    def test_retained_output_cannot_be_overwritten(self):
        retained = self.private/'retained'
        retained.mkdir()
        evidence = retained/'source.txt'
        evidence.write_text('unchanged evidence')
        with self.assertRaises(FileExistsError):
            tracer.new_output(retained, self.private)
        self.assertEqual(evidence.read_text(), 'unchanged evidence')

    def test_file_cannot_be_declared_private_root(self):
        root = self.private/'file'
        root.write_text('retained')
        with self.assertRaises(ValueError):
            tracer.new_output(root/'unexpected', root)
        self.assertEqual(root.read_text(), 'retained')

    def test_symlink_escape_is_resolved_before_scope_check(self):
        outside = self.base/'outside'
        outside.mkdir()
        link = self.private/'link'
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Directory symlinks unavailable: {error}')
        with self.assertRaises(ValueError):
            tracer.new_output(link/'unexpected', self.private)
        self.assertFalse((outside/'unexpected').exists())

    def test_dangling_output_link_cannot_create_a_new_target(self):
        target = self.private/'not-created'
        link = self.private/'retained-link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f'Directory symlinks unavailable: {error}')
        with self.assertRaises(FileExistsError):
            tracer.new_output(link, self.private)
        self.assertTrue(link.is_symlink())
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
