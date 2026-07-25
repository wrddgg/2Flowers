"""万物生花 API 配置"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 阿里云 DashScope
    dashscope_api_key: str = ""
    dashscope_base_url: str = ""
    qwen_base_url: str = ""

    # 模型
    qwen_vl_model: str = "qwen-vl-max"      # 视觉理解
    qwen_text_model: str = "qwen-turbo"     # 文本生成
    wan_image_model: str = "wan2.7-image"   # 文生图

    # 服务
    host: str = "0.0.0.0"
    port: int = 8001
    upload_dir: str = "./uploads"
    # 生成图片的公网访问基础地址（部署后通过 nginx /uploads/ 暴露）
    public_base: str = ""  # 例如 http://39.108.90.226 ；留空则用相对路径

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
