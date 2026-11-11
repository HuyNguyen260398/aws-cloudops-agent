"""Extract search queries from user prompts for tool semantic search."""


def extract_tool_query(prompt: str) -> str:
    """Extract key terms from user prompt for tool search.
    
    Args:
        prompt: User's input message
        
    Returns:
        Simplified query string for semantic tool search
    """
    # Remove common filler words
    stop_words = {
        'i', 'me', 'my', 'myself', 'we', 'our', 'ours', 'ourselves', 'you', 
        'your', 'yours', 'yourself', 'yourselves', 'he', 'him', 'his', 'himself',
        'she', 'her', 'hers', 'herself', 'it', 'its', 'itself', 'they', 'them',
        'their', 'theirs', 'themselves', 'what', 'which', 'who', 'whom', 'this',
        'that', 'these', 'those', 'am', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'having', 'do', 'does', 'did', 'doing',
        'a', 'an', 'the', 'and', 'but', 'if', 'or', 'because', 'as', 'until',
        'while', 'of', 'at', 'by', 'for', 'with', 'about', 'against', 'between',
        'into', 'through', 'during', 'before', 'after', 'above', 'below', 'to',
        'from', 'up', 'down', 'in', 'out', 'on', 'off', 'over', 'under', 'again',
        'further', 'then', 'once', 'can', 'could', 'should', 'would', 'please',
        'help', 'show', 'tell', 'give', 'get', 'need', 'want'
    }
    
    # Convert to lowercase and split
    words = prompt.lower().split()
    
    # Keep important words
    key_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Return first 10 words or the prompt if too short
    if len(key_words) < 3:
        return prompt[:100]
    
    return ' '.join(key_words[:10])
