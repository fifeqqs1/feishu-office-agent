from loguru import logger
from urllib.parse import urljoin
from fastapi import APIRouter, Body, UploadFile, File, Depends

from agentchat.api.services.user import UserPayload, get_login_user
from agentchat.schema.schemas import UnifiedResponseModel, resp_200, resp_500
from agentchat.services.storage import storage_client
from agentchat.settings import app_settings
from agentchat.utils.file_utils import get_object_storage_base_path

router = APIRouter(tags=["Upload"])

@router.post("/upload", description="上传文件的接口", response_model=UnifiedResponseModel)
async def upload_file(
    *,
    file: UploadFile = File(description="支持常见的Pdf、Docx、Txt、Jpg等文件"),
    login_user: UserPayload = Depends(get_login_user)
):
    try:
        file_content = await file.read()

        oss_object_name = get_object_storage_base_path(file.filename)
        # 先上传对象
        storage_client.upload_file(oss_object_name, file_content)

        # 返回可访问的URL：
        # - minio 使用预签名URL
        # - oss 使用公共 base_url 拼接的直链
        if app_settings.storage.mode == "minio":
            url = storage_client.sign_url_for_get(oss_object_name)
        else:
            url = urljoin(app_settings.storage.active.base_url, oss_object_name)

        return resp_200(url)
    except Exception as err:
        logger.error(f"上传文件{file.filename}出错：{err}")
        return resp_500(message=str(err))
