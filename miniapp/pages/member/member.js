const app = getApp()
Page({
  data: { members: [], keyword: '', branches: [], activeBranchId: 0 },
  onShow() { this.load() },
  async load() {
    try {
      const [membersRes, treeRes] = await Promise.all([
        app.request({ url: '/members/' }),
        app.request({ url: '/branches/tree' })
      ])
      // 展平树形结构为选项卡列表
      const tabs = this.flattenTree(treeRes || [])
      tabs.unshift({ id: 0, name: '全部', member_count: (membersRes || []).length })
      this.setData({
        members: membersRes || [],
        branches: tabs,
        activeBranchId: 0
      })
    } catch (e) {}
  },
  // 展平树：取出所有叶子支部（有 children 的为总支，跳过）
  flattenTree(nodes) {
    let result = []
    for (const node of nodes) {
      if (node.children && node.children.length > 0) {
        result = result.concat(this.flattenTree(node.children))
      } else {
        result.push(node)
      }
    }
    return result
  },
  onTabTap(e) {
    const branchId = e.currentTarget.dataset.id
    this.setData({ activeBranchId: branchId })
    if (branchId === 0) {
      this.loadAllMembers()
    } else {
      this.loadBranchMembers(branchId)
    }
  },
  async loadAllMembers() {
    try {
      const res = await app.request({ url: '/members/' })
      this.setData({ members: res || [], keyword: '' })
    } catch (e) {}
  },
  async loadBranchMembers(branchId) {
    try {
      const res = await app.request({ url: `/branches/${branchId}/members` })
      this.setData({ members: res || [], keyword: '' })
    } catch (e) {}
  },
  onSearch(e) {
    const kw = e.detail.value
    this.setData({ keyword: kw })
    if (!kw) {
      // 清空搜索时恢复当前 tab 数据
      if (this.data.activeBranchId === 0) {
        this.loadAllMembers()
      } else {
        this.loadBranchMembers(this.data.activeBranchId)
      }
      return
    }
    // 搜索全部会员
    this.search(kw)
  },
  async search(kw) {
    try {
      const res = await app.request({ url: `/members/?keyword=${encodeURIComponent(kw)}` })
      this.setData({ members: res || [] })
    } catch (e) {}
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/member/detail?id=${e.currentTarget.dataset.id}` })
  }
})
