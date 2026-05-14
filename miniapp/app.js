App({
  globalData: {
    userInfo: null,
    token: null,
    role: null, // 'public' | 'member' | 'candidate' | 'branch_leader' | 'org_leader' | 'admin'
    baseUrl: 'https://api.kaimin.org'
  },

  onLaunch() {
    // 检查登录状态
    const token = wx.getStorageSync('token')
    if (token) {
      this.globalData.token = token
      this.checkSession()
    }
  },

  checkSession() {
    wx.checkSession({
      success: () => {},
      fail: () => {
        this.globalData.token = null
        wx.removeStorageSync('token')
      }
    })
  },

  // 全局请求方法
  request(options) {
    const { url, method = 'GET', data, header = {} } = options
    return new Promise((resolve, reject) => {
      wx.request({
        url: `${this.globalData.baseUrl}${url}`,
        method,
        data,
        header: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.globalData.token}`,
          ...header
        },
        success(res) {
          if (res.statusCode === 200) {
            resolve(res.data)
          } else if (res.statusCode === 401) {
            wx.removeStorageSync('token')
            wx.navigateTo({ url: '/pages/index/index' })
            reject(res)
          } else {
            wx.showToast({ title: res.data.message || '请求失败', icon: 'none' })
            reject(res)
          }
        },
        fail(err) {
          wx.showToast({ title: '网络异常，请重试', icon: 'none' })
          reject(err)
        }
      })
    })
  }
})
