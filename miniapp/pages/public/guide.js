const app = getApp()
Page({
  data: { guide: null },
  onLoad() {
    try {
      app.request({ url: '/public/guide', noAuth: true }).then(res => {
        this.setData({ guide: res })
      })
    } catch (e) {}
  }
})
