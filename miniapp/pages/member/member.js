const app = getApp()
Page({
  data: { members: [], keyword: '', branches: [] },
  onShow() { this.load() },
  async load() {
    try {
      const [res, brs] = await Promise.all([
        app.request({ url: '/members/' }),
        app.request({ url: '/branches/tree' })
      ])
      this.setData({ members: res || [], branches: brs || [] })
    } catch (e) {}
  },
  onSearch(e) { this.setData({ keyword: e.detail.value }); this.search() },
  async search() {
    try { const res = await app.request({ url: `/members/?keyword=${this.data.keyword}` }); this.setData({ members: res || [] }) } catch (e) {}
  },
  goDetail(e) { wx.navigateTo({ url: `/pages/member/detail?id=${e.currentTarget.dataset.id}` }) }
})
