

class PrompBuilder():
    def build_prompt(self, question_request: str, context_content: list) -> str:
        return f"""
        answer question based on context：
        {''.join(context_content)}
        
        question：{question_request}
        answer：
        """

    def build_prompt_stream(self, question: str, context: str) -> str:
        """stream prompt template"""
        return f"""
        you are a professional IT expert with extensive troubleshooting experience, please answer the question based on the following context:
        {context}
        
        question：{question}
        
        please answer in a clear, step-by-step manner:
        """

    def build_prompt_retrieval(self, question_request: str) -> str:
        return f"""
        Is the following input a question? Reply only 'yes' or 'no'.\n\nInput: {question_request}
        """

    def build_prompt_stepback(self, question_request: str) -> str:
        return f"""
        You are a helpful assistant. Break down this query into a simpler or more general form to improve retrieval: \n\nOriginal Query: {question_request}

        Reply only the refined query.
        """

