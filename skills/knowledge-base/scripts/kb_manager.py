#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库管理脚本
功能：添加文档、检索查询、列表文档、删除文档、查看状态
"""

import os
import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path

# 配置
KB_BASE = Path.home() / ".openclaw" / "workspace" / "skills" / "knowledge-base"
DATA_DIR = KB_BASE / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
METADATA_FILE = DATA_DIR / "metadata.json"

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {
    '.pdf', '.docx', '.doc', '.txt', '.md', '.csv',
    '.py', '.js', '.ts', '.json', '.yaml', '.yml',
    '.html', '.css', '.xml', '.sql', '.sh'
}


def ensure_dependencies():
    """确保依赖已安装"""
    try:
        import chromadb
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain_community.vectorstores import Chroma
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install chromadb langchain langchain-community sentence-transformers pypdf python-docx")
        return False


def get_embeddings():
    """获取本地嵌入模型"""
    from langchain_community.embeddings import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )


def get_vectorstore():
    """获取向量存储"""
    from langchain_community.vectorstores import Chroma
    embeddings = get_embeddings()
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        collection_name="knowledge_base"
    )


def load_metadata():
    """加载元数据"""
    if METADATA_FILE.exists():
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"documents": {}}


def save_metadata(metadata):
    """保存元数据"""
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def generate_doc_id(file_path):
    """生成文档ID"""
    content = f"{file_path}_{datetime.now().isoformat()}"
    return hashlib.md5(content.encode()).hexdigest()[:12]


def extract_text_from_file(file_path):
    """从文件提取文本"""
    from langchain_community.document_loaders import (
        PyPDFLoader, Docx2txtLoader, TextLoader, CSVLoader
    )
    
    file_path = Path(file_path)
    ext = file_path.suffix.lower()
    
    try:
        if ext == '.pdf':
            loader = PyPDFLoader(str(file_path))
            docs = loader.load()
            return "\n\n".join([doc.page_content for doc in docs])
        
        elif ext in ['.docx', '.doc']:
            loader = Docx2txtLoader(str(file_path))
            docs = loader.load()
            return "\n\n".join([doc.page_content for doc in docs])
        
        elif ext == '.csv':
            loader = CSVLoader(str(file_path))
            docs = loader.load()
            return "\n\n".join([doc.page_content for doc in docs])
        
        else:  # 文本文件
            loader = TextLoader(str(file_path), encoding='utf-8')
            docs = loader.load()
            return "\n\n".join([doc.page_content for doc in docs])
    
    except Exception as e:
        raise Exception(f"文件解析失败: {e}")


def add_document(file_path):
    """添加文档到知识库"""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    ext = file_path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        print(f"❌ 不支持的文件格式: {ext}")
        print(f"支持的格式: {', '.join(SUPPORTED_EXTENSIONS)}")
        return False
    
    print(f"📄 正在处理: {file_path.name}")
    
    # 提取文本
    print("  ⏳ 提取文本...")
    try:
        text = extract_text_from_file(file_path)
    except Exception as e:
        print(f"  ❌ {e}")
        return False
    
    if not text.strip():
        print("  ❌ 文件内容为空")
        return False
    
    # 生成文档ID
    doc_id = generate_doc_id(file_path)
    
    # 分块
    print("  ⏳ 分块处理...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = splitter.split_text(text)
    documents = [
        Document(
            page_content=chunk,
            metadata={
                "doc_id": doc_id,
                "source": file_path.name,
                "chunk_index": i
            }
        )
        for i, chunk in enumerate(chunks)
    ]
    
    # 存入向量数据库
    print("  ⏳ 向量化存储（首次加载模型较慢）...")
    try:
        vectorstore = get_vectorstore()
        vectorstore.add_documents(documents)
    except Exception as e:
        print(f"  ❌ 存储失败: {e}")
        return False
    
    # 更新元数据
    print("  ⏳ 更新元数据...")
    metadata = load_metadata()
    metadata["documents"][doc_id] = {
        "id": doc_id,
        "filename": file_path.name,
        "path": str(file_path),
        "chunks": len(chunks),
        "added_at": datetime.now().isoformat(),
        "size": file_path.stat().st_size
    }
    save_metadata(metadata)
    
    print(f"  ✅ 添加成功!")
    print(f"     文档ID: {doc_id}")
    print(f"     文件名: {file_path.name}")
    print(f"     分块数: {len(chunks)}")
    return True


def search_knowledge(query, top_k=5):
    """检索知识库"""
    try:
        vectorstore = get_vectorstore()
        results = vectorstore.similarity_search_with_score(query, k=top_k)
        
        if not results:
            print("❌ 未找到相关内容")
            return []
        
        print(f"🔍 找到 {len(results)} 个相关片段:\n")
        
        output = []
        for i, (doc, score) in enumerate(results, 1):
            source = doc.metadata.get("source", "未知")
            content = doc.page_content[:300] + "..." if len(doc.page_content) > 300 else doc.page_content
            
            print(f"--- 片段 {i} (相似度: {1-score:.2%}) ---")
            print(f"来源: {source}")
            print(f"内容: {content}\n")
            
            output.append({
                "rank": i,
                "score": float(score),
                "source": source,
                "content": doc.page_content
            })
        
        return output
    
    except Exception as e:
        print(f"❌ 检索失败: {e}")
        return []


def list_documents():
    """列出所有文档"""
    metadata = load_metadata()
    docs = metadata.get("documents", {})
    
    if not docs:
        print("📋 知识库为空")
        return []
    
    print(f"📋 知识库共有 {len(docs)} 个文档:\n")
    print(f"{'ID':<12} {'文件名':<30} {'分块数':<8} {'添加时间'}")
    print("-" * 80)
    
    output = []
    for doc_id, doc_info in docs.items():
        print(f"{doc_id:<12} {doc_info['filename']:<30} {doc_info['chunks']:<8} {doc_info['added_at'][:10]}")
        output.append(doc_info)
    
    return output


def delete_document(doc_id):
    """删除文档"""
    metadata = load_metadata()
    docs = metadata.get("documents", {})
    
    if doc_id not in docs:
        print(f"❌ 文档不存在: {doc_id}")
        return False
    
    doc_info = docs[doc_id]
    print(f"🗑️ 正在删除: {doc_info['filename']}")
    
    # 从元数据删除
    del docs[doc_id]
    save_metadata(metadata)
    
    print(f"  ✅ 已从记录中删除")
    print(f"  ⚠️ 注意: 向量数据需重建数据库才能完全清理")
    return True


def show_status():
    """显示知识库状态"""
    metadata = load_metadata()
    docs = metadata.get("documents", {})
    
    total_chunks = sum(doc.get("chunks", 0) for doc in docs.values())
    total_size = sum(doc.get("size", 0) for doc in docs.values())
    
    print("📊 知识库状态\n")
    print(f"文档数量: {len(docs)}")
    print(f"总分块数: {total_chunks}")
    print(f"总大小: {total_size / 1024 / 1024:.2f} MB")
    print(f"存储路径: {CHROMA_DIR}")
    print(f"元数据: {METADATA_FILE}")
    print(f"嵌入模型: paraphrase-multilingual-MiniLM-L12-v2 (本地)")


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n用法:")
        print("  python3 kb_manager.py add <文件路径>     # 添加文档")
        print("  python3 kb_manager.py search \"<问题>\"   # 检索查询")
        print("  python3 kb_manager.py list              # 列出文档")
        print("  python3 kb_manager.py delete <文档ID>   # 删除文档")
        print("  python3 kb_manager.py status            # 查看状态")
        sys.exit(1)
    
    if not ensure_dependencies():
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "add":
        if len(sys.argv) < 3:
            print("❌ 请指定文件路径")
            sys.exit(1)
        add_document(sys.argv[2])
    
    elif command == "search":
        if len(sys.argv) < 3:
            print("❌ 请输入查询内容")
            sys.exit(1)
        search_knowledge(sys.argv[2])
    
    elif command == "list":
        list_documents()
    
    elif command == "delete":
        if len(sys.argv) < 3:
            print("❌ 请指定文档ID")
            sys.exit(1)
        delete_document(sys.argv[2])
    
    elif command == "status":
        show_status()
    
    else:
        print(f"❌ 未知命令: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
