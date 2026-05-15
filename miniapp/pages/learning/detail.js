const app = getApp()
Page({
  data: { detail: null, recordId: null, reading: false },
  onLoad(opts) { this.load(opts.id) },
  async load(id) {
    try {
      const res = await app.request({ url: `/learning/${id}` })
      this.setData({ detail: res })
      // 开始阅读计时
      this.startTime = Date.now()
    } catch (e) {}
  },
  onUnload() {
    this.completeReading()
  },
  // 完成阅读并记录时长
  completeReading() {
    if (!this.startTime || !this.data.detail) return
    const duration = Math.floor((Date.now() - this.startTime) / 1000)
    if (duration < 5) return // 少于5秒不记录
    // 查找 record，由于后端在 GET detail 时创建了 record，这里需要额外查询
    // 简化处理：直接调用后端完成接口（实际上 record 需要先存在）
    // 当前后端在 GET detail 时会创建 LearningRecord，这里调用 records/my 获取最新
    app.request({ url: '/learning/records/my' }).then(res => {
      const records = res || []
      const latest = records.find(r => r.is_completed === false)
      if (latest) {
        app.request({
          url: `/learning/records/${latest.id}/complete?duration_seconds=${duration}`,
          method: 'POST'
        })
      }
    }).catch(() => {})
  },
  goBack() { wx.navigateBack() }
})