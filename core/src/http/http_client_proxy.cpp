/*
 * http_client_proxy.cpp
 * 
 * Copyright (C) 2017-2031  YuHuan Chow <chowyuhuan@gmail.com>
 */

#include "http_client_proxy.hpp"

#include <glog/logging.h>

namespace core
{

http_client_proxy::http_client_proxy(const std::string& host,
                                     const std::string& port,
                                     const std::string& method,
                                     const std::string& path,
                                     const std::string& headers,
                                     const std::string& content,
                                     int timeout,
                                     bool usessl,
                                     bool keep_alive)
{
    // port headers usessl not support yet
    async_client c(io_service, host, path, method, content,
                   timeout, keep_alive,
                   boost::bind(&http_client_proxy::callback, this, 
                               boost::placeholders::_1,
                               boost::placeholders::_2,
                               boost::placeholders::_3));
}

http_client_proxy::~http_client_proxy()
{

}

void http_client_proxy::start()
{
    io_service.run();
}

void http_client_proxy::callback(const std::string& err, 
                                 const std::string& headers, 
                                 const std::string& content)
{
	DLOG(INFO) << __FUNCTION__ << " " << this;
}

http_client_proxy_wrapper::http_client_proxy_wrapper(PyObject *self,
                                                     const std::string& host,
                                                     const std::string& port,
                                                     const std::string& method,
                                                     const std::string& path,
                                                     const std::string& headers,
                                                     const std::string& content,
                                                     int timeout,
                                                     bool usessl,
                                                     bool keep_alive)
: http_client_proxy(host, port, method, path, headers, content, timeout, usessl, keep_alive),
  self_(self)
{
    boost::python::incref(self_);
}

http_client_proxy_wrapper::~http_client_proxy_wrapper()
{
    boost::python::decref(self_);
    self_ = NULL;
}

void http_client_proxy_wrapper::callback(const std::string& err, 
                                         const std::string& headers, 
                                         const std::string& content)
{
	DLOG(INFO) << __FUNCTION__ << " " << this;
    BEGIN_CALL_SCRIPT
        if(self_) boost::python::call_method<void>(self_, "callback", err, headers, content);
    END_CALL_SCRIPT
}

} // namespace core