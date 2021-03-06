from nxdrive.client import NotFound
from nxdrive.client import LocalClient
from nxdrive.tests.common import IntegrationTestCase
from shutil import copyfile
import hashlib
import time
import os


class TestIntegrationRemoteFileSystemClient(IntegrationTestCase):

    def setUp(self):
        super(TestIntegrationRemoteFileSystemClient, self).setUp()
        # Bind the test workspace as sync root for user 1
        remote_document_client = self.remote_document_client_1
        remote_fs_client = self.remote_file_system_client_1
        remote_document_client.register_as_root(self.workspace)

        # Fetch the id of the workspace folder item
        toplevel_folder_info = remote_fs_client.get_filesystem_root_info()
        self.workspace_id = remote_fs_client.get_children_info(
            toplevel_folder_info.uid)[0].uid

    #
    # Test the API common with the local client API
    #

    def test_get_info(self):
        remote_client = self.remote_file_system_client_1

        # Check file info
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        info = remote_client.get_info(fs_item_id)
        self.assertTrue(info is not None)
        self.assertEquals(info.name, 'Document 1.txt')
        self.assertEquals(info.uid, fs_item_id)
        self.assertEquals(info.parent_uid,
            self.workspace_id)
        self.assertFalse(info.folderish)
        digest_algorithm = info.digest_algorithm
        self.assertEquals(digest_algorithm, 'md5')
        digest = self._get_digest(digest_algorithm, "Content of doc 1.")
        self.assertEquals(info.digest, digest)
        file_uid = fs_item_id.rsplit("#", 1)[1]
        self.assertEquals(info.download_url,
            'nxbigfile/default/' + file_uid + '/blobholder:0/Document%201.txt')

        # Check folder info
        fs_item_id = remote_client.make_folder(self.workspace_id,
            'Folder 1')
        info = remote_client.get_info(fs_item_id)
        self.assertTrue(info is not None)
        self.assertEquals(info.name, 'Folder 1')
        self.assertEquals(info.uid, fs_item_id)
        self.assertEquals(info.parent_uid,
            self.workspace_id)
        self.assertTrue(info.folderish)
        self.assertTrue(info.digest_algorithm is None)
        self.assertTrue(info.digest is None)
        self.assertTrue(info.download_url is None)

        # Check non existing file info
        fs_item_id = self.FS_ITEM_ID_PREFIX + 'fakeId'
        self.assertRaises(NotFound,
            remote_client.get_info, fs_item_id)
        self.assertTrue(
            remote_client.get_info(fs_item_id,
                raise_if_missing=False) is None)

    def test_get_content(self):
        remote_client = self.remote_file_system_client_1

        # Check file with content
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        self.assertEquals(remote_client.get_content(fs_item_id),
            "Content of doc 1.")

        # Check file without content
        doc_uid = self.remote_document_client_1.make_file(self.workspace,
            'Document 2.txt')
        fs_item_id = self.FS_ITEM_ID_PREFIX + doc_uid
        self.assertRaises(NotFound,
            remote_client.get_content, fs_item_id)

    def test_stream_content(self):
        remote_client = self.remote_file_system_client_1

        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        file_path = os.path.join(self.local_test_folder_1, 'Document 1.txt')
        tmp_file = remote_client.stream_content(fs_item_id, file_path)
        self.assertTrue(os.path.exists(tmp_file))
        self.assertEquals(os.path.basename(tmp_file), '.Document 1.txt.part')
        self.assertEqual(open(tmp_file, 'rb').read(), "Content of doc 1.")

    def test_get_children_info(self):
        remote_client = self.remote_file_system_client_1

        # Create documents
        folder_1_id = remote_client.make_folder(self.workspace_id,
            'Folder 1')
        folder_2_id = remote_client.make_folder(self.workspace_id,
            'Folder 2')
        file_1_id = remote_client.make_file(self.workspace_id,
            'File 1', "Content of file 1.")
        file_2_id = remote_client.make_file(folder_1_id,
            'File 2', "Content of file 2.")

        # Check workspace children
        workspace_children = remote_client.get_children_info(self.workspace_id)
        self.assertTrue(workspace_children is not None)
        self.assertEquals(len(workspace_children), 3)
        self.assertEquals(workspace_children[0].uid, folder_1_id)
        self.assertEquals(workspace_children[0].name, 'Folder 1')
        self.assertTrue(workspace_children[0].folderish)
        self.assertEquals(workspace_children[1].uid, folder_2_id)
        self.assertEquals(workspace_children[1].name, 'Folder 2')
        self.assertTrue(workspace_children[1].folderish)
        self.assertEquals(workspace_children[2].uid, file_1_id)
        # the .txt name is added by the server to the title of Note
        # documents
        self.assertEquals(workspace_children[2].name, 'File 1.txt')
        self.assertFalse(workspace_children[2].folderish)

        # Check folder_1 children
        folder_1_children = remote_client.get_children_info(folder_1_id)
        self.assertTrue(folder_1_children is not None)
        self.assertEquals(len(folder_1_children), 1)
        self.assertEquals(folder_1_children[0].uid, file_2_id)
        self.assertEquals(folder_1_children[0].name, 'File 2.txt')

    def test_make_folder(self):
        remote_client = self.remote_file_system_client_1

        fs_item_id = remote_client.make_folder(self.workspace_id,
            'My new folder')
        self.assertTrue(fs_item_id is not None)
        info = remote_client.get_info(fs_item_id)
        self.assertTrue(info is not None)
        self.assertEquals(info.name, 'My new folder')
        self.assertTrue(info.folderish)
        self.assertTrue(info.digest_algorithm is None)
        self.assertTrue(info.digest is None)
        self.assertTrue(info.download_url is None)

    def test_make_file(self):
        remote_client = self.remote_file_system_client_1

        # Check File document creation
        fs_item_id = remote_client.make_file(self.workspace_id,
            'My new file.odt', "Content of my new file.")
        self.assertTrue(fs_item_id is not None)
        info = remote_client.get_info(fs_item_id)
        self.assertTrue(info is not None)
        self.assertEquals(info.name, 'My new file.odt')
        self.assertFalse(info.folderish)
        digest_algorithm = info.digest_algorithm
        self.assertEquals(digest_algorithm, 'md5')
        digest = self._get_digest(digest_algorithm, "Content of my new file.")
        self.assertEquals(info.digest, digest)

        # Check Note document creation
        fs_item_id = remote_client.make_file(self.workspace_id,
            'My new note.txt', "Content of my new note.")
        self.assertTrue(fs_item_id is not None)
        info = remote_client.get_info(fs_item_id)
        self.assertTrue(info is not None)
        self.assertEquals(info.name, 'My new note.txt')
        self.assertFalse(info.folderish)
        digest_algorithm = info.digest_algorithm
        self.assertEquals(digest_algorithm, 'md5')
        digest = self._get_digest(digest_algorithm, "Content of my new note.")
        self.assertEquals(info.digest, digest)

    def test_make_file_custom_encoding(self):
        remote_client = self.remote_file_system_client_1

        # Create content encoded in utf-8 and cp1252
        unicode_content = u'\xe9'  # e acute
        utf8_encoded = unicode_content.encode('utf-8')
        utf8_digest = hashlib.md5(utf8_encoded).hexdigest()
        cp1252_encoded = unicode_content.encode('cp1252')

        # Make files with this content
        utf8_fs_id = remote_client.make_file(self.workspace_id,
            'My utf-8 file.txt', utf8_encoded)
        cp1252_fs_id = remote_client.make_file(self.workspace_id,
            'My cp1252 file.txt', cp1252_encoded)

        # Check content
        utf8_content = remote_client.get_content(utf8_fs_id)
        self.assertEqual(utf8_content, utf8_encoded)
        cp1252_content = remote_client.get_content(cp1252_fs_id)
        self.assertEqual(cp1252_content, utf8_encoded)

        # Check digest
        utf8_info = remote_client.get_info(utf8_fs_id)
        self.assertEqual(utf8_info.digest, utf8_digest)
        cp1252_info = remote_client.get_info(cp1252_fs_id)
        self.assertEqual(cp1252_info.digest, utf8_digest)

    def test_update_content(self):
        remote_client = self.remote_file_system_client_1

        # Create file
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")

        # Check file update
        remote_client.update_content(
            fs_item_id, "Updated content of doc 1.")
        self.assertEquals(remote_client.get_content(fs_item_id),
            "Updated content of doc 1.")

    def test_delete(self):
        remote_client = self.remote_file_system_client_1

        # Create file
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        self.assertTrue(remote_client.exists(fs_item_id))

        # Delete file
        remote_client.delete(fs_item_id)
        self.assertFalse(remote_client.exists(fs_item_id))

    def test_exists(self):
        remote_client = self.remote_file_system_client_1

        # Check existing file system item
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        self.assertTrue(remote_client.exists(fs_item_id))

        # Check non existing file system item (non existing document)
        fs_item_id = self.FS_ITEM_ID_PREFIX + 'fakeId'
        self.assertFalse(remote_client.exists(fs_item_id))

        # Check non existing file system item (document without content)
        doc_uid = self.remote_document_client_1.make_file(self.workspace,
            'Document 2.txt')
        # Wait to be sure that the file creation has been committed
        # See https://jira.nuxeo.com/browse/NXP-10964
        time.sleep(1.0)
        fs_item_id = self.FS_ITEM_ID_PREFIX + doc_uid
        self.assertFalse(remote_client.exists(fs_item_id))

    # TODO
    def test_check_writable(self):
        pass

    #
    # Test the API specific to the remote file system client
    #

    def test_get_fs_item(self):
        remote_client = self.remote_file_system_client_1

        # Check file item
        fs_item_id = remote_client.make_file(self.workspace_id,
            'Document 1.txt', "Content of doc 1.")
        fs_item = remote_client.get_fs_item(fs_item_id)
        self.assertTrue(fs_item is not None)
        self.assertEquals(fs_item['name'], 'Document 1.txt')
        self.assertEquals(fs_item['id'], fs_item_id)
        self.assertFalse(fs_item['folder'])

        # Check folder item
        fs_item_id = remote_client.make_folder(self.workspace_id,
            'Folder 1')
        fs_item = remote_client.get_fs_item(fs_item_id)
        self.assertTrue(fs_item is not None)
        self.assertEquals(fs_item['name'], 'Folder 1')
        self.assertEquals(fs_item['id'], fs_item_id)
        self.assertTrue(fs_item['folder'])

        # Check non existing file system item
        fs_item_id = self.FS_ITEM_ID_PREFIX + 'fakeId'
        self.assertTrue(remote_client.get_fs_item(fs_item_id)
                        is None)

    def test_get_top_level_children(self):
        remote_document_client = self.remote_document_client_1
        remote_file_system_client = self.remote_file_system_client_1

        # The workspace is registered as a sync root in the setup
        children = remote_file_system_client.get_top_level_children()
        self.assertEquals(len(children), 1)
        self.assertEquals(children[0]['name'], self.workspace_title)

        # Create 2 remote folders inside the workspace sync root
        fs_item_1_id = remote_file_system_client.make_folder(
            self.workspace_id, 'Folder 1')
        fs_item_2_id = remote_file_system_client.make_folder(
            self.workspace_id, 'Folder 2')
        folder_1_uid = fs_item_1_id.rsplit("#", 1)[1]
        folder_2_uid = fs_item_2_id.rsplit("#", 1)[1]

        # Unregister the workspace
        remote_document_client.unregister_as_root(self.workspace)
        children = remote_file_system_client.get_top_level_children()
        self.assertEquals(children, [])

        # Register the sub folders as new roots
        remote_document_client.register_as_root(folder_1_uid)
        remote_document_client.register_as_root(folder_2_uid)
        children = remote_file_system_client.get_top_level_children()
        self.assertEquals(len(children), 2)

        # Unregister one sync root
        remote_document_client.unregister_as_root(folder_1_uid)
        children = remote_file_system_client.get_top_level_children()
        self.assertEquals(len(children), 1)

    def test_conflicted_item_name(self):
        remote_file_system_client = self.remote_file_system_client_1
        new_name = remote_file_system_client.conflicted_name("My File.doc")
        self.assertTrue(new_name.startswith(
            "My File (nuxeoDriveTestUser_user_1 - "))
        self.assertTrue(new_name.endswith(").doc"))

    def test_streaming_upload(self):
        remote_client = self.remote_file_system_client_1

        # Create a document by streaming a text file
        file_path = remote_client.make_tmp_file("Some content.")
        fs_item_id = remote_client.stream_file(self.workspace_id, file_path,
                                               filename='My streamed file.txt')
        self.assertEquals(remote_client.get_info(fs_item_id).name,
                        'My streamed file.txt')
        self.assertEquals(remote_client.get_content(fs_item_id),
                          "Some content.")

        # Update a document by streaming a new text file
        file_path = remote_client.make_tmp_file("Other content.")
        remote_client.stream_update(fs_item_id, file_path,
                                    filename='My updated file.txt')
        self.assertEquals(remote_client.get_info(fs_item_id).name,
                        'My updated file.txt')
        self.assertEquals(remote_client.get_content(fs_item_id),
                          "Other content.")

        # Create a document by streaming a binary file
        file_path = os.path.join(self.upload_tmp_dir, 'testFile.pdf')
        copyfile('nxdrive/tests/resources/testFile.pdf', file_path)
        fs_item_id = remote_client.stream_file(self.workspace_id, file_path)
        local_client = LocalClient(self.upload_tmp_dir)
        fs_item_info = remote_client.get_info(fs_item_id)
        self.assertEquals(fs_item_info.name, 'testFile.pdf')
        self.assertEquals(fs_item_info.digest,
                          local_client.get_info('/testFile.pdf').get_digest())

    def _get_digest(self, digest_algorithm, content):
        hasher = getattr(hashlib, digest_algorithm)
        if hasher is None:
            raise RuntimeError('Unknown digest algorithm: %s'
                % digest_algorithm)
        return hasher(content).hexdigest()
