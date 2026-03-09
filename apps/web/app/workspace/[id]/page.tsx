import { redirect } from "next/navigation";

export default async function WorkspaceIndexPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(`/workspace/${id}/integrations`);
}
