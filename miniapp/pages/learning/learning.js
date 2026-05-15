const app = getApp()
Page({
  data: { materials: [], category: '', keyword: '' },
  onLoad() { this.load() },
  async load() {
    let params = []
    if (this.data.category) params.push('category=' + this.data.category)
    if (this.data.keyword) params.push('keyword=' + this.data.keyword)
    const qs = params.length > 0 ? '?' + params.join('&') : ''
    try {
      const res = await app.request({ url: `/learning/${qs}` })
      this.setData({ materials: res || [] })
    } catch (e) {}
  },
  onSearch(e) {
    this.setData({ keyword: e.detail.value })
    this.load()
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/learning/detail?id=${id}` })
  }
})
