-- İnceleyip onayladıktan sonra mevcut Supabase projesinde tek işlem olarak çalıştırın.
-- Bu nesneler repo şemasında oluşturulmuyor; gerçek projede önceden var olmaları gerekir.
-- İstemci uygulamalar anon/authenticated erişimi kullanıyorsa bu işlem onları keser.
-- v_ileri_test_ozet postgres sahibi ile RLS'yi aşarak toplulaştırılmış veri gösterebilir.
-- service_role kullanan botun mevcut erişimini korur; hiçbir satır silmez.
begin;
revoke all privileges on table public.gece_raporu from public, anon, authenticated;
revoke all privileges on table public.ileri_test from public, anon, authenticated;
revoke all privileges on table public.v_ileri_test_ozet from public, anon, authenticated;
grant select, insert, update on table public.gece_raporu, public.ileri_test to service_role;
grant select on table public.v_ileri_test_ozet to service_role;
commit;
