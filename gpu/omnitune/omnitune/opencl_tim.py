DEVINFOS = [
  {
    "address_bits": 32,
    "double_fp_config": 63,
    "endian_little": 1,
    "execution_capabilities": 1,
    "extensions": "cl_khr_byte_addressable_store cl_khr_icd cl_khr_gl_sharing cl_nv_compiler_options cl_nv_device_attribute_query cl_nv_pragma_unroll  cl_khr_global_int32_base_atomics cl_khr_global_int32_extended_atomics cl_khr_local_int32_base_atomics cl_khr_local_int32_extended_atomics cl_khr_fp64",
    "global_mem_cache_size": 262144,
    "global_mem_cache_type": 2,
    "global_mem_cacheline_size": 128,
    "global_mem_size": 1610285056,
    "host_unified_memory": 0,
    "image2d_max_height": 32768,
    "image2d_max_width": 32768,
    "image3d_max_depth": 2048,
    "image3d_max_height": 2048,
    "image3d_max_width": 2048,
    "image_support": 1,
    "local_mem_size": 49152,
    "local_mem_type": 1,
    "max_clock_frequency": 1215,
    "max_compute_units": 1,
    "max_constant_args": 9,
    "max_constant_buffer_size": 65536,
    "max_mem_alloc_size": 402571264,
    "max_parameter_size": 4352,
    "max_read_image_args": 128,
    "max_samplers": 16,
    "max_work_group_size": 1024,
    "max_work_item_dimensions": 3,
    "max_work_item_sizes_0": 1024,
    "max_work_item_sizes_1": 1024,
    "max_work_item_sizes_2": 4,
    "max_write_image_args": 8,
    "mem_base_addr_align": 4096,
    "min_data_type_align_size": 128,
    "name": "GeForce GTX 590",
    "native_vector_width_char": 1,
    "native_vector_width_double": 1,
    "native_vector_width_float": 1,
    "native_vector_width_half": 1,
    "native_vector_width_int": 1,
    "native_vector_width_long": 1,
    "native_vector_width_short": 1,
    "preferred_vector_width_char": 1,
    "preferred_vector_width_double": 1,
    "preferred_vector_width_float": 1,
    "preferred_vector_width_half": 1,
    "preferred_vector_width_int": 1,
    "preferred_vector_width_long": 1,
    "preferred_vector_width_short": 1,
    "queue_properties": 3,
    "single_fp_config": 63,
    "type": 4,
    "vendor": "nvidia corporation",
    "vendor_id": "10deh",
    "version": "opencl 1.1 cuda",
  }
]


def get_devinfos():
  """
  Return a list of device info dicts for each device on system.
  """
  return DEVINFOS
