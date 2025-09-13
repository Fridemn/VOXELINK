import axios from 'axios'

export const addCancelToken = config => {
  const source = axios.CancelToken.source()
  config.cancelToken = source.token
  return source
}

export const cancelRequest = (source, msg = '请求已取消') => {
  source.cancel(msg)
}