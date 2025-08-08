import json
from langchain_core.document_loaders import BaseLoader
from typing import List
from langchain.schema import Document


class JSONLoader(BaseLoader):
    """支持结构化解析的自定义JSON加载器"""

    def __init__(self, file_path: str):
        self.file_path = file_path

    def load(self) -> List[Document]:
        from langchain.docstore.document import Document

        try:
            # 根据文件名选择解析模式
            if "CRM" in Path(self.file_path).name:
                chunks = parse_json(self.file_path)
            else:
                chunks = parse_json_generic(self.file_path)

            return [
                Document(
                    page_content=chunk,
                    metadata={
                        "source": self.file_path,
                        "format": "json"
                    }
                ) for chunk in chunks
            ]
        except Exception as e:
            logger.warning(f"JSON解析失败 {self.file_path}: {str(e)}")
            return []

    def parse_json(file_path):
        """解析知识库JSON文件，提取结构化文本"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        documents = []
        for issue in data.get("issues", []):
            title = issue.get("title", "")
            for scenario in issue.get("scenarios", []):
                # 组合所有字段为自然语言描述
                content = f"""
                [Issue] {title}
                Observation: {scenario.get('observation', '')}
                Symptom: {scenario.get('symptom', '')}
                Root Cause: {scenario.get('root_cause', '')}
                Workaround Steps:
                {chr(10).join(scenario.get('workaround', []))}
                Permanent Solution: {scenario.get('solution', '')}
                """
                ocuments.append(content.strip())
        return documents

    def parse_json_generic(file_path, sep="\n"):
        """通用JSON解析器，自动提取结构化文本"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        documents = []

        def _traverse(obj, path=""):
            """递归遍历所有数据结构"""
            content = []

            if isinstance(obj, dict):
                for k, v in obj.items():
                    new_path = f"{path}.{k}" if path else k
                    content.append(_traverse(v, new_path))

            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]"
                    content.append(_traverse(item, new_path))

            else:  # 叶子节点
                if obj is None:
                    return ""
                str_value = str(obj).strip()
                if str_value:
                    # 保留数据结构路径作为上下文
                    return f"[{path}] {str_value}" if path else str_value
                return ""

            return sep.join(filter(None, content))

        root_content = _traverse(data)

        # 按段落长度自动分块
        max_chunk = 1000
        chunks = []
        current_chunk = []
        current_length = 0

        for line in root_content.split(sep):
            line_len = len(line)
            if current_length + line_len > max_chunk and current_chunk:
                chunks.append(sep.join(current_chunk))
                current_chunk = []
                current_length = 0
            current_chunk.append(line)
            current_length += line_len

        if current_chunk: 
            chunks.append(sep.join(current_chunk))

        return chunks
