const app = getApp()
Page({
  data: { items: [], page: 1, hasMore: true, loading: false },
  onLoad() { this.load() },
  async load() {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const res = await app.request({
        url: `/public/news?page=${this.data.page}&size=10`,
        noAuth: true
      })
      const items = res.items || []
      this.setData({
        items: this.data.page === 1 ? items : [...this.data.items, ...items],
        hasMore: items.length === 10,
        loading: false
      })
    } catch (e) {
      this.setData({ loading: false })
    }
  },
  loadMore() {
    if (!this.data.hasMore || this.data.loading) return
    this.setData({ page: this.data.page + 1 })
    this.load()
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/public/news-detail?id=${id}` })
  }
})