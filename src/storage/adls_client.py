
from azure.storage.filedatalake import DataLakeServiceClient

class ADLSClient:
    def __init__(self, 
                account_url: str,
                credential: str,
                file_system: str):
        self.service_client = DataLakeServiceClient(
            account_url=f"https://{account_url}.dfs.core.windows.net",
            credential=credential,
        )
        self.filesystem_client = self.service_client.get_file_system_client(file_system)
    
    def get_directory_client(self, path: str):
            return self.filesystem_client.get_directory_client(path)

    def get_file_client(self, path: str):
        return self.filesystem_client.get_file_client(path)

    def list_paths(self, path: str):
        return self.filesystem_client.get_paths(path=path)