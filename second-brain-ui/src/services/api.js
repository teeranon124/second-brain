/**
 * API Client for Backend Communication
 */

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class APIClient {
  constructor(baseURL = API_URL) {
    this.baseURL = baseURL;
  }

  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Request failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      throw error;
    }
  }

  // ==================== GENERIC HTTP METHODS ====================

  async get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }

  async post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }

  // ==================== GRAPH OPERATIONS ====================

  async getFullGraph() {
    return this.request('/api/graph');
  }

  // ==================== NODE OPERATIONS ====================

  async getNodes() {
    return this.request('/api/nodes');
  }

  async getNode(nodeId) {
    return this.request(`/api/nodes/${nodeId}`);
  }

  async createNode(nodeData) {
    return this.request('/api/nodes', {
      method: 'POST',
      body: JSON.stringify(nodeData),
    });
  }

  async updateNode(nodeId, nodeData) {
    return this.request(`/api/nodes/${nodeId}`, {
      method: 'PUT',
      body: JSON.stringify(nodeData),
    });
  }

  async deleteNode(nodeId) {
    return this.request(`/api/nodes/${nodeId}`, {
      method: 'DELETE',
    });
  }

  // ==================== LINK OPERATIONS ====================

  async getLinks() {
    return this.request('/api/links');
  }

  async createLink(linkData) {
    return this.request('/api/links', {
      method: 'POST',
      body: JSON.stringify(linkData),
    });
  }

  async updateLink(linkId, linkData) {
    return this.request(`/api/links/${linkId}`, {
      method: 'PUT',
      body: JSON.stringify(linkData),
    });
  }

  async deleteLink(linkId) {
    return this.request(`/api/links/${linkId}`, {
      method: 'DELETE',
    });
  }

  // ==================== QUERY & RAG OPERATIONS ====================

  async queryGraph(query, maxHops = 3, topK = 2) {
    return this.request('/api/query', {
      method: 'POST',
      body: JSON.stringify({
        query,
        max_hops: maxHops,
        top_k: topK,
      }),
    });
  }

  async extractEntities(text) {
    return this.request('/api/query/extract', {
      method: 'POST',
      body: JSON.stringify({
        text,
        extract_links: true,
      }),
    });
  }

  // ==================== DOCUMENT OPERATIONS ====================

  async parseDocument(file) {
    const formData = new FormData();
    formData.append('file', file);

    const url = `${this.baseURL}/api/documents/parse`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        // ไม่ต้องใส่ Content-Type เพราะ browser จะ set boundary ให้อัตโนมัติ
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(error.detail || `HTTP ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Document parse error:', error);
      throw error;
    }
  }

  // ==================== BULK OPERATIONS ====================

  async bulkCreateNodes(nodes) {
    return this.request('/api/graph/bulk/nodes', {
      method: 'POST',
      body: JSON.stringify(nodes),
    });
  }

  async bulkCreateLinks(links) {
    return this.request('/api/graph/bulk/links', {
      method: 'POST',
      body: JSON.stringify(links),
    });
  }

  // ==================== BATCH CREATE (WITH ENTITY MATCHING) ====================

  async batchCreate({ nodes, links, book }) {
    /**
     * Batch create nodes + links with entity matching and deduplication
     * 
     * Returns:
     *   {
     *     nodes: NodeResponse[],
     *     links: LinkResponse[],
     *     stats: {new_nodes, merged_nodes, new_links, skipped_links}
     *   }
     */
    return this.request('/api/nodes/batch-create', {
      method: 'POST',
      body: JSON.stringify({ nodes, links, book }),
    });
  }

  // ==================== HEALTH CHECK ====================

  async healthCheck() {
    return this.request('/health');
  }

  // ==================== BOOK NOTEBOOK ====================

  async getBooks() {
    return this.request('/api/books');
  }

  async getBook(bookId) {
    return this.request(`/api/books/${bookId}`);
  }

  async getBookClusters() {
    return this.request('/api/books/clusters/overview');
  }

  async updateBook(bookId, payload) {
    return this.request(`/api/books/${bookId}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
  }

  async deleteBook(bookId) {
    return this.request(`/api/books/${bookId}`, {
      method: 'DELETE',
    });
  }

  async getBooksByNode(nodeId) {
    return this.request(`/api/books/by-node/${nodeId}`);
  }

  async getQuizBooks() {
    return this.request('/api/quiz/books');
  }

  async getQuizQuestionByBook(bookId, difficulty = 'medium') {
    return this.request(`/api/quiz/by-book/${bookId}/question?difficulty=${encodeURIComponent(difficulty)}`);
  }
}

// Export singleton instance
export const api = new APIClient();
export default api;
