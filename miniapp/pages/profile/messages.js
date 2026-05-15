const app = getApp()
Page({
  data: { messages: [], page: 1, hasMore: true },
  onShow() { this.setData({ page: 1, messages: [] }); this.load() },
  async load() {
    try {
      const res = await app.request({ url: `/profile/messages?page=${this.data.page}&size=20` })
      const items = res.items || []
      this.setData({
        messages: this.data.page === 1 ? items : [...this.data.messages, ...items],
        hasMore: items.length === 20
      })
    } catch (e) {}
  },
  loadMore() {
    if (!this.data.hasMore) return
    this.setData({ page: this.data.page + 1 })
    this.load()
  },
  async goDetail(e) {
    const { id, link } = e.currentTarget.dataset
    // 标记已读
    try { await app.request({ url: `/profile/messages/${id}/read`, method: 'POST' }) } catch (e) {}
    this.setData({
      messages: this.data.messages.map(m => m.id === id ? { ...m, is_read: true } : m)
    })
    if (link) {
      wx.navigateTo({ url: link })
    }
  },
  async markAllRead() {
    try {
      await app.request({ url: '/profile/messages/read-all', method: 'POST' })
      this.setData({
        messages: this.data.messages.map(m => ({ ...m, is_read: true }))
      })
      wx.showToast({ title: '已全部已读', icon: 'success' })
    } catch (e) {}
  }
})